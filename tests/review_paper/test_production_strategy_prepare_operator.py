"""Fake-only qualification of the production decision through accepted PREPARE."""

import ast
import json
import logging
import os
import warnings
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from tests.review_paper.test_production_strategy_cycle import _decision

from scripts import checkpoint_runner
from trading_bot import production_strategy_prepare_operator as subject
from trading_bot.market_calendar import TradingSession
from trading_bot.review_paper import production_strategy_cycle, risk_price_acquisition
from trading_bot.review_paper import supervised_forward_paper as supervised
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp import sdk_transport, windows_oauth

AT = datetime(2026, 10, 2, 16, tzinfo=UTC)
TARGET = AT.date()
RUN = subject.run_production_strategy_shadow_prepare
SECRET = "https://private.invalid/?code=secret-provider-material"


def decision(*, no_signal=False, target=TARGET):
    value = _decision(no_signal=no_signal)
    return replace(
        value,
        contract=replace(value.contract, target_session_date=target),
        prepared=replace(
            value.prepared, intended_execution_session=TradingSession(target)
        ),
    )


@pytest.fixture
def harness(tmp_path, monkeypatch):
    value = decision()
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    inputs = dict(
        decision=value,
        store=store,
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(seconds=60),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        expected_branch="feature/robinhood-production-strategy-live-paper",
        expected_source_head=value.contract.source_head,
        expected_source_tree=value.contract.source_tree,
        evidence_path=tmp_path / "evidence.json",
        redirect_uri="http://127.0.0.1:8765/callback",
    )
    # Real source admission has separate focused coverage; source tests are dirty.
    roots = (Path(subject.__file__).resolve().parents[2],)
    admit = Mock(return_value=roots)
    monkeypatch.setattr(subject, "admit_robinhood_paper_source", admit)
    native = Mock(side_effect=AssertionError("real protected effect"))
    for owner, name in (
        (windows_oauth.WindowsCredentialApi, "read_generic"),
        (windows_oauth.WindowsCredentialApi, "write_generic"),
        (windows_oauth.WindowsOAuthStorage, "get_tokens"),
        (windows_oauth.WindowsOAuthStorage, "get_client_info"),
        (windows_oauth.LoopbackOAuthCallback, "redirect_handler"),
        (windows_oauth.LoopbackOAuthCallback, "callback_handler"),
        (sdk_transport.RobinhoodMcpStreamableHttpTransport, "_request_once"),
        (supervised, "execute_review_paper_supervised_cycle"),
        (supervised, "run_robinhood_forward_paper_cycle"),
        (production_strategy_cycle, "execute_review_paper_supervised_cycle"),
        (production_strategy_cycle, "execute_production_strategy_paper_cycle"),
        (ReviewPaperStore, "record_market_review"),
    ):
        monkeypatch.setattr(owner, name, native)
    calls = []
    quote = {
        "symbol": str(value.proposal.symbol),
        "adjusted_previous_close": "100",
        "ask_price": "101",
        "bid_price": "99",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "100",
        "previous_close": "100",
        "previous_close_date": None,
        "state": "active",
        "venue_ask_time": AT.isoformat(),
        "venue_bid_time": AT.isoformat(),
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": AT.isoformat(),
    }

    async def caller(name, arguments):
        calls.append((name, arguments))
        assert name == "get_equity_quotes"
        observed = risk_price_acquisition.datetime.now.return_value
        for key in ("venue_ask_time", "venue_bid_time", "venue_last_trade_time"):
            quote[key] = observed.isoformat()
        return {"data": {"results": [{"quote": quote, "close": None}]}}

    transport = sdk_transport.RobinhoodMcpStreamableHttpTransport.for_test(caller)
    constructor = Mock(return_value=transport)
    oauth = Mock(return_value=lambda: None)
    monkeypatch.setattr(subject, "RobinhoodMcpStreamableHttpTransport", constructor)
    monkeypatch.setattr(subject, "create_windows_robinhood_oauth_factory", oauth)
    clock = Mock()
    clock.now.return_value = AT
    monkeypatch.setattr(supervised, "datetime", clock)
    monkeypatch.setattr(
        risk_price_acquisition, "datetime", Mock(now=Mock(return_value=AT))
    )
    accepted_prepare = subject.prepare_production_strategy_paper_cycle

    def prepare_once(**kwargs):
        delegate.actual_result = accepted_prepare(**kwargs)
        return delegate.actual_result

    delegate = Mock(side_effect=prepare_once)
    monkeypatch.setattr(subject, "prepare_production_strategy_paper_cycle", delegate)
    yield inputs, calls, oauth, constructor, delegate, native, admit
    native.assert_not_called()


def evidence(inputs):
    return json.loads(inputs["evidence_path"].read_text())


@pytest.mark.parametrize("mode", ["ready", "no_signal", "session", "expired", "risk"])
def test_real_composition_status_evidence_and_zero_mutation(harness, monkeypatch, mode):
    inputs, calls, oauth, constructor, delegate, _, admit = harness
    before = inputs["store"].path.read_bytes()
    if mode == "no_signal":
        inputs["decision"] = decision(no_signal=True)
        # Neither properties nor methods of these surfaces can be used.
        for key in (
            "store",
            "opening_buffer",
            "closing_buffer",
            "max_quote_age",
            "risk_limits",
            "new_trading_enabled",
            "redirect_uri",
        ):
            inputs[key] = object()
    elif mode == "session":
        supervised.datetime.now.return_value = AT.replace(hour=12)
    elif mode == "expired":
        risk_price_acquisition.datetime.now.return_value = AT.replace(hour=20)
    elif mode == "risk":
        inputs["new_trading_enabled"] = False
    result = RUN(**inputs)
    assert result.decision is inputs["decision"]
    assert result is delegate.actual_result
    assert delegate.call_count == 1
    assert delegate.call_args.kwargs["decision"] is inputs["decision"]
    expected = {
        "ready": "READY_TO_PROCEED",
        "no_signal": "NO_SIGNAL",
        "session": "SESSION_NOT_ADMITTED",
        "expired": "SESSION_EXPIRED_DURING_ACQUISITION",
        "risk": "RISK_REJECTED",
    }[mode]
    assert result.status.value == expected
    data = evidence(inputs)
    assert data["decision_status"] == inputs["decision"].status.value
    assert data["prepare_status"] == expected
    assert data["source_head"] == inputs["decision"].contract.source_head
    assert data["source_tree"] == inputs["decision"].contract.source_tree
    assert data["contract_id"] == str(inputs["decision"].contract.contract_id)
    assert data["target_session_date"] == AT.date().isoformat()
    assert data["durable_before"] == data["durable_after"]
    assert data["durable_observed"] == (mode != "no_signal")
    assert data["execute_invoked"] is False and data["pipeline_result_present"] is False
    count = int(mode not in {"no_signal", "session"})
    assert data["get_equity_quotes_calls"] == count
    assert len(calls) == count
    assert all(
        data[name] == 0
        for name in (
            "get_accounts_calls",
            "get_equity_orders_calls",
            "review_equity_order_calls",
            "placement_calls",
            "cancellation_calls",
            "options_mutation_calls",
            "crypto_mutation_calls",
        )
    )
    assert oauth.call_count == constructor.call_count == (mode != "no_signal")
    if mode == "no_signal":
        assert data["proposal"] is None and data["durable_before"] is None
    else:
        assert data["proposal"] == {
            "proposal_id": str(result.decision.proposal.proposal_id),
            "symbol": str(result.decision.proposal.symbol),
            "side": result.decision.proposal.side.value,
            "desired_quantity": str(result.decision.proposal.desired_quantity),
        }
        assert result.supervised.proposal is inputs["decision"].proposal
        assert inputs["store"].path.read_bytes() == before
    if count:
        assert data["quote_observed_at"] is not None
    if mode in {"ready", "risk"}:
        assert data["quote_valid_until"] == (AT + timedelta(seconds=60)).isoformat()
        assert (
            data["risk_outcome"] is not None and data["approved_quantity"] is not None
        )
    assert admit.call_count == 2


@pytest.mark.parametrize(
    "kind",
    [
        "wrong_type",
        "head",
        "tree",
        "source",
        "non_session",
        "unsupported",
        "existing",
        "relative",
        "store",
        "directory",
        "mixed_import",
    ],
)
def test_failures_before_effects(harness, monkeypatch, kind):
    inputs, calls, oauth, _, delegate, _, _ = harness
    if kind == "wrong_type":
        inputs["decision"] = object()
    elif kind in {"head", "tree"}:
        inputs["expected_source_" + kind] = "c" * 40
    elif kind == "source":
        monkeypatch.setattr(
            subject,
            "admit_robinhood_paper_source",
            Mock(side_effect=RuntimeError(SECRET)),
        )
    elif kind in {"non_session", "unsupported"}:
        inputs["decision"] = decision(
            target=date(2026, 10, 3) if kind == "non_session" else date(2025, 1, 7)
        )
    elif kind == "existing":
        inputs["evidence_path"].write_text("preserve")
    elif kind == "relative":
        inputs["evidence_path"] = Path("relative.json")
    elif kind == "store":
        inputs["evidence_path"] = inputs["store"].path
    elif kind == "directory":
        inputs["evidence_path"] = (
            inputs["evidence_path"].parent / "missing" / "file.json"
        )
    elif kind == "mixed_import":
        monkeypatch.setitem(
            subject.sys.modules, "trading_bot.invalid", Mock(__file__=__file__)
        )
    with pytest.raises(
        (TypeError, subject.ProductionStrategyPrepareOperatorError)
    ) as caught:
        RUN(**inputs)
    assert SECRET not in str(caught.value)
    assert not calls
    oauth.assert_not_called()
    delegate.assert_not_called()
    if kind == "existing":
        assert inputs["evidence_path"].read_text() == "preserve"


def test_lookup_is_exact_and_once(harness, monkeypatch):
    inputs, *_ = harness
    lookup = Mock(wraps=NYSEPublishedRegularSessionAuthority.schedule_for)
    monkeypatch.setattr(
        NYSEPublishedRegularSessionAuthority,
        "schedule_for",
        lambda self, target: lookup(self, target),
    )
    RUN(**inputs)
    lookup.assert_called_once()
    assert lookup.call_args.args[1] is inputs["decision"].contract.target_session_date


def test_quote_budget_and_forbidden_reads():
    transport = Mock()
    guarded = subject._QuoteOnlyTransport(transport)
    for name in ("get_equity_orders", "review_equity_order"):
        with pytest.raises(subject.ProductionStrategyPrepareOperatorError):
            getattr(guarded, name)({})
    transport.assert_not_called()
    assert not hasattr(guarded, "get_accounts")
    transport.get_equity_quotes.side_effect = RuntimeError(SECRET)
    with pytest.raises(RuntimeError):
        guarded.get_equity_quotes({})
    with pytest.raises(subject.ProductionStrategyPrepareOperatorError):
        guarded.get_equity_quotes({})
    transport.get_equity_quotes.assert_called_once_with({})
    assert guarded.quote_calls == 1


def test_oauth_blocker_and_provider_error_are_sanitized(harness, monkeypatch, capfd):
    inputs, calls, oauth, _, delegate, _, _ = harness
    with pytest.raises(windows_oauth.LoopbackOAuthError) as caught:
        subject._block_interactive_authorization(SECRET)
    assert SECRET not in str(caught.value)

    def fail(**kwargs):
        print(SECRET)
        print(SECRET, file=subject.sys.stderr)
        os.write(1, SECRET.encode())
        logging.error(SECRET)
        warnings.warn(SECRET, stacklevel=1)
        raise RuntimeError(SECRET)

    monkeypatch.setattr(subject, "prepare_production_strategy_paper_cycle", fail)
    with pytest.raises(subject.ProductionStrategyPrepareOperatorError) as caught:
        RUN(**inputs)
    assert str(caught.value) == "Shadow PREPARE stopped"
    assert caught.value.__suppress_context__
    assert SECRET not in "".join(capfd.readouterr())
    assert inputs["evidence_path"].read_text() == ""
    assert not calls
    oauth.assert_called_once()
    assert (
        oauth.call_args.kwargs["browser_opener"]
        is subject._block_interactive_authorization
    )
    delegate.assert_not_called()


@pytest.mark.parametrize("failure", ["provider", "drift", "final_source"])
def test_terminal_failure_no_second_prepare(harness, monkeypatch, failure):
    inputs, calls, _, constructor, delegate, _, admit = harness
    if failure == "provider":

        async def fail(name, arguments):
            calls.append((name, arguments))
            raise RuntimeError(SECRET)

        constructor.return_value = (
            sdk_transport.RobinhoodMcpStreamableHttpTransport.for_test(fail)
        )
    elif failure == "drift":
        original = subject.qualification_fingerprint
        results = 0

        def fingerprint(*args):
            nonlocal results
            results += 1
            result = original(*args)
            return result if results == 1 else {**result, "sha256": "0" * 64}

        monkeypatch.setattr(subject, "qualification_fingerprint", fingerprint)
    elif failure == "final_source":
        admit.side_effect = [admit.return_value, RuntimeError(SECRET)]
    with pytest.raises(subject.ProductionStrategyPrepareOperatorError) as caught:
        RUN(**inputs)
    assert SECRET not in str(caught.value)
    assert delegate.call_count == 1
    assert len(calls) == 1
    assert inputs["evidence_path"].read_text() == ""


def test_no_execution_retry_or_strategy_authority_in_source():
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8-sig"))
    forbidden = {
        "execute_production_strategy_paper_cycle",
        "execute_review_paper_supervised_cycle",
        "run_robinhood_forward_paper_cycle",
        "record_market_review",
        "build_production_strategy_decision",
        "ProductionStrategyContract",
        "sleep",
        "retry",
        "poll",
        "get_accounts",
        "place_order",
        "cancel_order",
    }
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.While, ast.AsyncFunctionDef))
        if isinstance(node, (ast.Name, ast.Attribute)):
            assert (
                node.id if isinstance(node, ast.Name) else node.attr
            ) not in forbidden
    spec = checkpoint_runner._checkpoint_specs()[
        "arch134-production-strategy-live-paper"
    ]
    assert (
        "tests/review_paper/test_production_strategy_prepare_operator.py" in spec.tests
    )
    assert "src/trading_bot/production_strategy_prepare_operator.py" in spec.ruff_paths
    assert spec.preflight is None and spec.execute is None


def test_risk_resize_is_evidence_only(harness):
    inputs, calls, _, _, delegate, _, _ = harness
    inputs["risk_limits"] = RiskLimits(max_order_notional=Decimal("100"))
    result = RUN(**inputs)
    data = evidence(inputs)
    assert data["risk_outcome"] == "RESIZED"
    assert (
        Decimal(data["approved_quantity"]) < result.decision.proposal.desired_quantity
    )
    assert result is delegate.actual_result
    assert len(calls) == 1
    assert data["execute_invoked"] is False


def test_source_gate_pins_the_complete_operator(tmp_path):
    source = Path(subject.__file__)
    assert checkpoint_runner._git_blob_sha1(source) == (
        checkpoint_runner.ARCH134_PRODUCTION_STRATEGY_PREPARE_OPERATOR_PIN
    )
    root = source.resolve().parents[2]
    assert (
        checkpoint_runner._arch134_production_strategy_live_paper_authority_check(root)
        == ()
    )


def test_actual_source_admission_rejects_unreviewed_source(harness, monkeypatch):
    from trading_bot.robinhood_paper_operator import admit_robinhood_paper_source

    inputs, calls, oauth, _, delegate, _, _ = harness
    monkeypatch.setattr(
        subject, "admit_robinhood_paper_source", admit_robinhood_paper_source
    )
    with pytest.raises(subject.ProductionStrategyPrepareOperatorError):
        RUN(**inputs)
    assert not calls
    oauth.assert_not_called()
    delegate.assert_not_called()


def test_evidence_reservation_race_stops_before_oauth(harness, monkeypatch):
    inputs, calls, oauth, _, delegate, _, _ = harness
    original_open = Path.open

    def collide(path, *args, **kwargs):
        if path == inputs["evidence_path"] and args == ("x",):
            with original_open(path, "w") as output:
                output.write("preserve competing evidence")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", collide)
    with pytest.raises(subject.ProductionStrategyPrepareOperatorError):
        RUN(**inputs)
    assert inputs["evidence_path"].read_text() == "preserve competing evidence"
    assert not calls
    oauth.assert_not_called()
    delegate.assert_not_called()


def test_publication_failure_does_not_reprepare(harness, monkeypatch):
    inputs, calls, _, _, delegate, _, _ = harness
    original_dumps = subject.json.dumps

    def fail(payload, **kwargs):
        if (
            isinstance(payload, dict)
            and payload.get("schema") == "production-strategy-shadow-prepare/v1"
        ):
            raise RuntimeError(SECRET)
        return original_dumps(payload, **kwargs)

    monkeypatch.setattr(subject.json, "dumps", fail)
    with pytest.raises(subject.ProductionStrategyPrepareOperatorError):
        RUN(**inputs)
    assert delegate.call_count == 1 and len(calls) == 1
    assert inputs["evidence_path"].read_text() == ""
