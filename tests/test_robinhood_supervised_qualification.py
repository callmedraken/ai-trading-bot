"""131-V doubles: real 131-Q guards, fixture SQLite, zero provider access."""

from __future__ import annotations

import ast
import io
import json
import sqlite3
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

import trading_bot.review_paper.supervised_forward_paper as supervised
import trading_bot.robinhood_execute_qualification_verifier as verifier
import trading_bot.robinhood_supervised_qualification as gate
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.review_paper.intent_bridge import build_review_paper_intent
from trading_bot.review_paper.models import (
    ReviewPaperIntent,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
)
from trading_bot.review_paper.prepare_qualification import (
    run_review_paper_prepare_qualification,
)
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskLimits, RiskOutcome
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_paper_operator import RobinhoodPaperOperatorEvidence
from trading_bot.robinhood_paper_pipeline import (
    RobinhoodDeterministicPaperPipelineResult,
)

AT = datetime(2026, 10, 5, 17, 30, tzinfo=UTC)
HEAD, TREE = "a" * 40, "b" * 40


def _review(side, price, at, *, reviewed_at=None):
    quote = RobinhoodReviewQuote(
        Symbol("SPY"),
        price,
        price,
        price,
        True,
        None,
        price,
        price,
        None,
        "active",
        at,
        at,
        None,
        at,
    )
    return RobinhoodEquityOrderReview(
        Symbol("SPY"),
        side,
        OrderType.MARKET,
        Decimal("1.000"),
        quote,
        "{}",
        at if reviewed_at is None else reviewed_at,
        "fixture disclosure",
    )


def _seed(store):
    for identity, price in ((1, "769.870000"), (2, "773.030000")):
        at = AT - timedelta(days=identity)
        intent = ReviewPaperIntent(
            UUID(int=identity),
            UUID(int=100 + identity),
            Symbol("SPY"),
            OrderSide.BUY,
            Decimal("1.000"),
            Decimal("1.000"),
            RiskOutcome.APPROVED,
            (),
            "fixture",
            None,
            OrderType.MARKET,
            TimeInForce.DAY,
            at,
        )
        store.record_market_review(intent, _review(OrderSide.BUY, Decimal(price), at))


class Terminal(io.StringIO):
    def __init__(self, h, capsys):
        super().__init__()
        self.h, self.capsys, self.reads = h, capsys, 0

    def isatty(self):
        return True

    def read(self, *args):
        assert args == ()
        self.reads += 1
        assert self.h.execute.call_count == 0 and self.h.forward.call_count == 0
        self.h.request = json.loads(self.capsys.readouterr().out)
        if self.h.on_read:
            self.h.on_read()
        else:
            self.h.execute_at = AT + timedelta(seconds=1)
        token = "AUTHORIZE 131-Q EXECUTE " + self.h.request["challenge"] + "\n"
        if self.h.answer == "raise":
            raise OSError("private secret upstream")
        return token if self.h.answer == "exact" else self.h.answer


@pytest.fixture
def h(tmp_path, monkeypatch, capsys):
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("100000"))
    _seed(store)
    inputs = dict(
        session_date=AT.date(),
        store_path=store.path,
        intended_store_path=store.path,
        expected_before_sha256=verifier.qualification_fingerprint(
            *verifier.read_qualification_store(store.path)
        )["sha256"],
        proposal=TradeProposal(
            verifier.PROPOSAL_ID,
            Symbol("SPY"),
            OrderSide.SELL,
            Decimal("1.000"),
            AT - timedelta(minutes=1),
            "fixture",
        ),
        order_id=verifier.ORDER_ID,
        risk_limits=RiskLimits(),
        expected_branch=verifier.BRANCH,
        expected_head=HEAD,
        expected_tree=TREE,
        prepare_evidence_path=tmp_path / "prepare.json",
        execute_evidence_path=tmp_path / "execute.json",
        operator_evidence_path=tmp_path / "operator.json",
        redirect_uri="http://127.0.0.1:8765/callback",
        slippage_basis_points=Decimal("0"),
        commission=Decimal("0"),
    )
    value = SimpleNamespace(
        inputs=inputs,
        store=store,
        answer="exact",
        on_read=None,
        request=None,
        execute_at=AT,
        preparation=None,
        forward_failure=False,
        operator_status="PASS",
        review_quote_offset=timedelta(0),
    )
    monkeypatch.setattr(gate, "_admit_source", Mock(return_value=tmp_path / "repo"))
    monkeypatch.setattr(gate, "_quiet_provider", nullcontext)
    monkeypatch.setattr(
        gate, "datetime", SimpleNamespace(now=lambda tz: value.execute_at)
    )
    monkeypatch.setattr(
        supervised, "datetime", SimpleNamespace(now=lambda tz: value.execute_at)
    )
    snapshot = ReviewPaperRiskPriceSnapshot(
        AT, (ReviewPaperRiskPriceMark(Symbol("SPY"), Decimal("775.00"), AT),)
    )
    value.acquire = Mock(return_value=snapshot)
    monkeypatch.setattr(
        supervised, "acquire_review_paper_risk_price_snapshot", value.acquire
    )

    def prepare(**kwargs):
        kwargs.pop("session_date")
        kwargs.pop("redirect_uri")
        kwargs["schedule"] = gate.NYSEPublishedRegularSessionAuthority().schedule_for(
            AT.date()
        )
        kwargs["adapter"] = object.__new__(RobinhoodReviewReadAdapter)
        value.preparation = run_review_paper_prepare_qualification(**kwargs)
        return value.preparation

    value.prepare = Mock(side_effect=prepare)
    monkeypatch.setattr(
        gate, "run_robinhood_published_session_prepare_qualification", value.prepare
    )
    value.prepare_verify = Mock(wraps=gate.verify_robinhood_prepare_qualification)
    monkeypatch.setattr(
        gate, "verify_robinhood_prepare_qualification", value.prepare_verify
    )
    value.execute = Mock(wraps=gate.execute_review_paper_supervised_cycle)
    monkeypatch.setattr(gate, "execute_review_paper_supervised_cycle", value.execute)

    def forward(**kwargs):
        assert value.terminal.reads == 1 and value.request is not None
        assert (
            kwargs["prices"] == snapshot.prices
            and kwargs["as_of"] == snapshot.observed_at
        )
        if value.forward_failure:
            raise RuntimeError("private exception OAuth account secret")
        decision = value.preparation.preview.risk_decision
        intent = build_review_paper_intent(
            decision, kwargs["instruction"], order_id=kwargs["order_id"]
        )
        if value.operator_status == "PASS":
            kwargs["store"].record_market_review(
                intent,
                _review(
                    OrderSide.SELL,
                    Decimal("774.00"),
                    kwargs["review_received_at"] + value.review_quote_offset,
                    reviewed_at=kwargs["review_received_at"],
                ),
            )
        operator = RobinhoodPaperOperatorEvidence(
            HEAD,
            TREE,
            value.operator_status,
            "complete",
            "SPY",
            "SELL",
            "1.000",
            "MARKET",
            1,
            2,
            1,
            0,
            1,
            1,
            len(kwargs["store"].history()),
            False,
            True,
            True,
            True,
            0,
        )
        kwargs["evidence_path"].write_text(
            json.dumps(asdict(operator)), encoding="utf-8"
        )
        return RobinhoodDeterministicPaperPipelineResult(decision, intent, operator)

    value.forward = Mock(side_effect=forward)
    monkeypatch.setattr(supervised, "run_robinhood_forward_paper_cycle", value.forward)
    value.terminal = Terminal(value, capsys)
    monkeypatch.setattr(sys, "stdin", value.terminal)
    # No production boundary is reachable even if a double is accidentally removed.
    value.forbidden = Mock(side_effect=AssertionError("real provider reached"))
    import trading_bot.robinhood_prepare_operator as provider

    monkeypatch.setattr(
        provider, "create_windows_robinhood_oauth_factory", value.forbidden
    )
    monkeypatch.setattr(
        provider, "RobinhoodMcpStreamableHttpTransport", value.forbidden
    )
    for name in ("equity_quotes", "review_market_order", "agentic_equity_orders"):
        monkeypatch.setattr(RobinhoodReviewReadAdapter, name, value.forbidden)
    return value


def _run(h):
    return gate.run_robinhood_supervised_qualification(**h.inputs)


def _verify(h):
    return verifier.verify_robinhood_execute_qualification(
        store_path=h.store.path,
        evidence_path=h.inputs["execute_evidence_path"],
        prepare_evidence_path=h.inputs["prepare_evidence_path"],
        operator_evidence_path=h.inputs["operator_evidence_path"],
        expected_source_head=HEAD,
        expected_source_tree=TREE,
        expected_before_sha256=h.inputs["expected_before_sha256"],
    )


def _evidence(h):
    return verifier.read_qualification_json(h.inputs["execute_evidence_path"])


def test_same_preparation_one_prepare_one_verifier_one_stdin_one_execute_one_forward(h):
    assert _run(h)["status"] == "PASS"
    assert (
        h.prepare.call_count == h.prepare_verify.call_count == h.acquire.call_count == 1
    )
    assert h.terminal.reads == h.execute.call_count == h.forward.call_count == 1
    assert h.execute.call_args.kwargs["preparation"] is h.preparation
    assert (
        h.execute.call_args.kwargs["instruction"].created_at
        >= h.preparation.preview.risk_decision.evaluated_at
    )
    assert len(h.store.history()) == 3
    assert _verify(h)["status"] == "PASS"
    assert set(_evidence(h)) == verifier.EVIDENCE_FIELDS
    h.forbidden.assert_not_called()


def test_verifier_allows_venue_fill_after_execute_admission(h):
    h.review_quote_offset = timedelta(seconds=1)
    assert _run(h)["status"] == "PASS"
    record = h.store.history()[-1]
    assert record.filled_at > h.execute_at
    assert _verify(h)["status"] == "PASS"


@pytest.mark.parametrize(
    "answer",
    [
        "",
        "\n",
        "wrong challenge\n",
        "AUTHORIZE 131-Q EXECUTE " + "0" * 64 + "\n",
        "raise",
        "AUTHORIZE 131-Q EXECUTE invalid\nsecond line\n",
    ],
)
def test_bad_token_blank_eof_error_stops_without_execute_or_retry(h, answer):
    h.answer = answer
    with pytest.raises(gate.SupervisedQualificationError, match="no retry"):
        _run(h)
    assert (
        h.terminal.reads
        == h.prepare.call_count
        == h.prepare_verify.call_count
        == h.acquire.call_count
        == 1
    )
    h.execute.assert_not_called()
    h.forward.assert_not_called()
    assert (
        _evidence(h)["authorization_accepted"] is False and len(h.store.history()) == 2
    )
    assert "secret" not in h.inputs["execute_evidence_path"].read_text()


@pytest.mark.parametrize("suffix", ["\n", "second line\n", " ", "\r\n"])
def test_exact_challenge_with_extra_input_is_rejected(h, suffix):
    original_read = h.terminal.read
    h.terminal.read = lambda: original_read() + suffix
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    h.execute.assert_not_called()
    assert h.terminal.reads == 1


@pytest.mark.parametrize("drift", ["expiry", "session", "history", "risk"])
def test_accepted_q_revalidation_stops_before_forward(h, monkeypatch, drift):
    def on_read():
        if drift == "expiry":
            h.execute_at = AT + timedelta(minutes=5, microseconds=1)
        elif drift == "session":
            h.execute_at = AT.replace(hour=20)
        elif drift == "history":
            history = h.preparation.durable_history
            monkeypatch.setattr(ReviewPaperStore, "history", lambda self: history[::-1])
        else:
            original = supervised.build_review_paper_forward_preview

            def different(**kwargs):
                preview = original(**kwargs)
                return replace(
                    preview,
                    risk_decision=replace(
                        preview.risk_decision,
                        outcome=RiskOutcome.RESIZED,
                        approved_quantity=Decimal("0.500"),
                    ),
                )

            monkeypatch.setattr(
                supervised, "build_review_paper_forward_preview", different
            )

    h.on_read = on_read
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    assert (
        h.execute.call_count
        == h.prepare.call_count
        == h.acquire.call_count
        == h.terminal.reads
        == 1
    )
    h.forward.assert_not_called()
    evidence = _evidence(h)
    assert (
        evidence["status"] == "INDETERMINATE"
        and evidence["forward_cycle_invoked"] is None
    )


@pytest.mark.parametrize(
    "boundary", ["prepare", "prepare_verify", "execute", "forward"]
)
def test_boundary_failure_no_retry_no_secret_disclosure(h, boundary):
    if boundary == "forward":
        h.forward_failure = True
    else:
        getattr(h, boundary).side_effect = RuntimeError("secret private raw exception")
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    assert (
        h.prepare.call_count == 1
        and h.execute.call_count <= 1
        and h.forward.call_count <= 1
    )
    assert "secret" not in h.inputs["execute_evidence_path"].read_text()
    if boundary in {"prepare", "prepare_verify"}:
        assert h.terminal.reads == 0
        h.execute.assert_not_called()


def test_operator_fail_never_certifies_or_retries(h):
    h.operator_status = "FAIL"
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    assert h.forward.call_count == h.execute.call_count == 1
    assert _evidence(h)["status"] == "FAIL"
    with pytest.raises(verifier.ExecuteQualificationVerificationError):
        _verify(h)


@pytest.mark.parametrize(
    "mode",
    [
        "wrong-store",
        "wrong-before",
        "existing-prepare",
        "existing-execute",
        "existing-operator",
        "same-evidence",
        "store-sidecar",
        "nonterminal",
        "wrong-order",
        "wrong-proposal",
        "wrong-policy",
        "non-session",
    ],
)
def test_admission_stops_before_prepare_provider(h, monkeypatch, mode):
    if mode == "wrong-store":
        h.inputs["store_path"] = Path(str(h.store.path) + "2")
    elif mode == "wrong-before":
        h.inputs["expected_before_sha256"] = "0" * 64
    elif mode.startswith("existing-"):
        key = mode.split("-")[1] + "_evidence_path"
        h.inputs[key].write_text("preserve", encoding="utf-8")
    elif mode == "same-evidence":
        h.inputs["execute_evidence_path"] = h.inputs["prepare_evidence_path"]
    elif mode == "store-sidecar":
        h.inputs["execute_evidence_path"] = Path(str(h.store.path) + "-wal")
    elif mode == "nonterminal":
        monkeypatch.setattr(h.terminal, "isatty", lambda: False)
    elif mode == "wrong-order":
        h.inputs["order_id"] = UUID(int=1)
    elif mode == "wrong-proposal":
        h.inputs["proposal"] = replace(h.inputs["proposal"], proposal_id=UUID(int=1))
    elif mode == "wrong-policy":
        h.inputs["slippage_basis_points"] = Decimal("1")
    else:
        h.inputs["session_date"] = AT.date() + timedelta(days=5)
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    h.prepare.assert_not_called()
    h.execute.assert_not_called()
    assert h.terminal.reads == 0
    if mode.startswith("existing-"):
        assert h.inputs[key].read_text() == "preserve"


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "v2"),
        ("source_head", "c" * 40),
        ("source_tree", "c" * 40),
        ("proposal_id", str(UUID(int=1))),
        ("order_id", str(UUID(int=2))),
        ("authorization_challenge", "0" * 64),
        ("authorization_accepted", False),
        ("authorization_accepted_at", (AT - timedelta(seconds=1)).isoformat()),
        ("instruction_created_at", (AT - timedelta(seconds=1)).isoformat()),
        ("quote_observed_at", (AT - timedelta(seconds=1)).isoformat()),
        ("quote_valid_until", (AT + timedelta(minutes=6)).isoformat()),
        ("prepare_evidence_sha256", "0" * 64),
        ("prepare_evidence_path", "wrong"),
        ("execute_calls", 2),
        ("stdin_reads", 2),
        ("prepare_calls", 2),
        ("prepare_verifier_calls", 0),
        ("forward_cycle_invoked", False),
        ("execute_invoked", False),
        ("retry_count", 1),
        ("placement_calls", 1),
        ("cancellation_calls", 1),
        ("options_mutation_calls", 1),
        ("crypto_mutation_calls", 1),
        ("interactive_reauth_count", 1),
        ("status", "FAIL"),
        ("durable_before", {}),
        ("durable_after", {}),
        ("revalidated_risk", {}),
        ("operator_evidence_sha256", "0" * 64),
        ("execute_admission", {}),
    ],
)
def test_verifier_independently_rejects_mutations(h, field, value):
    _run(h)
    evidence = _evidence(h)
    evidence[field] = value
    h.inputs["execute_evidence_path"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(verifier.ExecuteQualificationVerificationError):
        _verify(h)


@pytest.mark.parametrize("target", ["execute", "prepare", "operator"])
@pytest.mark.parametrize("mutation", ["extra", "missing", "duplicate"])
def test_verifier_exact_closed_schema(h, target, mutation):
    _run(h)
    path = h.inputs[target + "_evidence_path"]
    value = verifier.read_qualification_json(path)
    if mutation == "extra":
        value["unexpected"] = "private"
    elif mutation == "missing":
        value.pop(next(iter(value)))
    encoded = json.dumps(value)
    if mutation == "duplicate":
        key = next(iter(value))
        encoded = (
            encoded[:-1] + "," + json.dumps(key) + ":" + json.dumps(value[key]) + "}"
        )
    path.write_text(encoded, encoding="utf-8")
    with pytest.raises(verifier.ExecuteQualificationVerificationError):
        _verify(h)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE review_fills SET approved_quantity='2.000' WHERE side='SELL'",
        "UPDATE review_fills SET fill_price='1' WHERE side='SELL'",
        "UPDATE review_fills SET risk_outcome='RESIZED' WHERE side='SELL'",
        "UPDATE review_fills SET order_id='wrong' WHERE side='SELL'",
        "UPDATE review_fills SET proposal_id='wrong' WHERE side='SELL'",
        "UPDATE review_fills SET time_in_force='GTC' WHERE side='SELL'",
        "UPDATE review_fills SET order_checks_json='changed' WHERE side='BUY'",
        "DELETE FROM review_fills WHERE side='SELL'",
    ],
)
def test_verifier_rejects_current_durable_mutations(h, sql):
    _run(h)
    with sqlite3.connect(h.store.path) as connection:
        connection.execute(sql)
    with pytest.raises(verifier.ExecuteQualificationVerificationError):
        _verify(h)


def test_verifier_is_read_only_and_provider_free_in_fresh_process(h):
    _run(h)
    before = h.store.path.read_bytes()
    root = Path(gate.__file__).resolve().parents[2]
    args = [
        str(h.inputs[key])
        for key in (
            "store_path",
            "execute_evidence_path",
            "prepare_evidence_path",
            "operator_evidence_path",
        )
    ]
    code = """import sys, importlib.abc
class NoProvider(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if 'robinhood_mcp' in fullname or 'supervised_forward_paper' in fullname:
            raise AssertionError('provider/executor imported')
sys.meta_path.insert(0, NoProvider())
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from trading_bot.robinhood_execute_qualification_verifier import (
    verify_robinhood_execute_qualification,
)
result=verify_robinhood_execute_qualification(store_path=Path(sys.argv[2]),evidence_path=Path(sys.argv[3]),prepare_evidence_path=Path(sys.argv[4]),operator_evidence_path=Path(sys.argv[5]),expected_source_head=sys.argv[6],expected_source_tree=sys.argv[7],expected_before_sha256=sys.argv[8])
assert result['status']=='PASS'
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(root / "src"),
            *args,
            HEAD,
            TREE,
            h.inputs["expected_before_sha256"],
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert h.store.path.read_bytes() == before


def test_verifier_does_not_depend_on_ambient_decimal_context(h):
    _run(h)
    with localcontext() as context:
        context.prec = 2
        assert _verify(h)["status"] == "PASS"


def test_source_contains_no_generic_gate_injection_or_effect_paths():
    source = Path(gate.__file__).read_text()
    tree = ast.parse(source)
    public = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "run_robinhood_supervised_qualification"
    )
    parameters = {arg.arg for arg in public.args.kwonlyargs}
    assert not parameters & {
        "stdin",
        "reader",
        "callback",
        "execute",
        "adapter",
        "transport",
    }
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert (
        sum(
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "read"
            and ast.unparse(node.func.value) == "sys.stdin"
            for node in calls
        )
        == 1
    )
    assert not any(
        isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree)
    )
    assert not any(
        name in source
        for name in (
            "place_order(",
            "cancel_order(",
            "sleep(",
            "uuid4(",
            "run_robinhood_forward_paper_cycle(",
        )
    )


@pytest.mark.parametrize(
    "drift",
    [
        None,
        "branch",
        "head",
        "tree",
        "index",
        "tracked",
        "remote-url",
        "remote-head",
        "remote-tree",
        "module",
    ],
)
def test_source_admission_exact_remote_clean_state_and_loaded_provenance(
    monkeypatch, drift
):
    root = Path(gate.__file__).resolve().parents[2]
    ref = "refs/heads/" + verifier.BRANCH
    outputs = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): verifier.BRANCH,
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("status", "--porcelain", "--untracked-files=no"): "",
        ("diff", "--cached", "--name-only"): "",
        (
            "remote",
            "get-url",
            "origin",
        ): "https://github.com/callmedraken/ai-trading-bot.git",
        ("ls-remote", "origin", ref): HEAD + "\t" + ref,
        ("rev-parse", "origin/" + verifier.BRANCH): HEAD,
        ("rev-parse", "origin/" + verifier.BRANCH + "^{tree}"): TREE,
    }
    mutations = {
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "index": ("diff", "--cached", "--name-only"),
        "tracked": ("status", "--porcelain", "--untracked-files=no"),
        "remote-url": ("remote", "get-url", "origin"),
        "remote-head": ("ls-remote", "origin", ref),
        "remote-tree": ("rev-parse", "origin/" + verifier.BRANCH + "^{tree}"),
    }
    if drift in mutations:
        outputs[mutations[drift]] = "wrong"
    if drift == "module":
        monkeypatch.setitem(
            sys.modules,
            "trading_bot.foreign",
            SimpleNamespace(__file__=str(root.parent / "foreign.py")),
        )
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda args, **kwargs: SimpleNamespace(stdout=outputs[tuple(args[3:])]),
    )
    if drift:
        with pytest.raises(verifier.ExecuteQualificationVerificationError):
            gate._admit_source(verifier.BRANCH, HEAD, TREE)
    else:
        assert gate._admit_source(verifier.BRANCH, HEAD, TREE) == root


def test_qualification_launcher_pins_exact_store_and_bootstraps_own_source(
    monkeypatch, tmp_path
):
    import importlib.util

    root = Path(gate.__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "qualification_launcher", root / "scripts/robinhood_supervised_qualification.py"
    )
    launcher = importlib.util.module_from_spec(spec)
    old_path = sys.path[:]
    try:
        spec.loader.exec_module(launcher)
        assert sys.path[0] == str(root / "src")
    finally:
        sys.path[:] = old_path
    expected = Path(
        r"F:\AI\temp\robinhood-131j-source-live-91b4bf7f665947f79a6a94fd44ecae39\paper.sqlite"
    )
    assert launcher._INTENDED_STORE == expected
    run = Mock(side_effect=gate.SupervisedQualificationError("stop"))
    monkeypatch.setattr(launcher, "run_robinhood_supervised_qualification", run)
    argv = [
        "launcher",
        "--session-date",
        "2026-10-05",
        "--proposal-id",
        str(verifier.PROPOSAL_ID),
        "--order-id",
        str(verifier.ORDER_ID),
        "--proposal-created-at",
        AT.isoformat(),
        "--store",
        str(expected) + "2",
        "--prepare-evidence",
        str(tmp_path / "p.json"),
        "--execute-evidence",
        str(tmp_path / "e.json"),
        "--operator-evidence",
        str(tmp_path / "o.json"),
        "--expected-branch",
        verifier.BRANCH,
        "--expected-head",
        HEAD,
        "--expected-tree",
        TREE,
        "--expected-before-sha256",
        "0" * 64,
        "--redirect-uri",
        "http://127.0.0.1:8765/callback",
        "--slippage-basis-points",
        "0",
        "--commission",
        "0",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert launcher.main() == 1
    assert run.call_args.kwargs["intended_store_path"] == expected
    assert run.call_args.kwargs["store_path"] != expected


def test_lazy_performance_exports_preserve_identity():
    import trading_bot.review_paper as package
    import trading_bot.review_paper.performance as performance

    for name in package._PERFORMANCE_EXPORTS:
        assert getattr(package, name) is getattr(performance, name)
    with pytest.raises(AttributeError):
        _ = package.missing_export


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization_accepted_at", AT.replace(tzinfo=None).isoformat()),
        ("execute_admission.as_of", (AT + timedelta(minutes=6)).isoformat()),
        ("execute_admission.as_of", AT.replace(hour=20).isoformat()),
        ("execute_admission.opens_at", AT.replace(hour=13, minute=0).isoformat()),
        ("execution_configuration.commission", "1"),
        ("execution_configuration.slippage_basis_points", "1"),
        ("execution_configuration.max_quote_age_seconds", 600),
        ("execution_configuration.time_in_force", "GTC"),
        ("prepared_risk.approved_quantity", "0.500"),
        ("operator_evidence.replay", True),
        ("operator_evidence.get_equity_quotes_calls", 1),
        ("execute_calls", True),
    ],
)
def test_verifier_nested_identity_and_timestamp_mutations(h, field, value):
    _run(h)
    evidence = _evidence(h)
    keys = field.split(".")
    target = evidence
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    h.inputs["execute_evidence_path"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(verifier.ExecuteQualificationVerificationError):
        _verify(h)


@pytest.mark.parametrize("target", ["prepare-evidence", "metadata"])
def test_authorization_pause_drift_stops_before_execute(h, target):
    def change():
        if target == "prepare-evidence":
            with h.inputs["prepare_evidence_path"].open(
                "a", encoding="utf-8"
            ) as output:
                output.write(" ")
        else:
            with sqlite3.connect(h.store.path) as connection:
                connection.execute(
                    "UPDATE metadata SET value='100001' WHERE key='starting_cash'"
                )

    h.on_read = change
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    h.execute.assert_not_called()
    h.forward.assert_not_called()
    assert h.terminal.reads == 1


@pytest.mark.parametrize("failure", [False, True])
def test_provider_output_logs_warnings_and_fds_are_discarded(capfd, failure):
    import logging
    import os
    import warnings

    prior_handle = logging.Logger.handle

    def noisy():
        with gate._quiet_provider():
            print("private-payload")
            print("private-payload", file=sys.stderr)
            os.write(1, b"private-payload")
            os.write(2, b"private-payload")
            logging.getLogger("provider").critical("private-payload")
            warnings.warn("private-payload", stacklevel=1)
            if failure:
                raise RuntimeError("private-payload")

    if failure:
        with pytest.raises(RuntimeError):
            noisy()
    else:
        noisy()
    assert capfd.readouterr() == ("", "")
    assert logging.Logger.handle is prior_handle


def test_prepare_evidence_drift_during_independent_verification_stops(h):
    original = h.prepare_verify._mock_wraps

    def verify_then_change(**kwargs):
        result = original(**kwargs)
        with h.inputs["prepare_evidence_path"].open("a", encoding="utf-8") as output:
            output.write(" ")
        return result

    h.prepare_verify.side_effect = verify_then_change
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    assert h.prepare_verify.call_count == 1 and h.terminal.reads == 0
    h.execute.assert_not_called()


def test_second_invocation_with_fresh_paths_cannot_replay_qualification(h):
    _run(h)
    for field in (
        "prepare_evidence_path",
        "execute_evidence_path",
        "operator_evidence_path",
    ):
        h.inputs[field] = h.inputs[field].with_name("second-" + h.inputs[field].name)
    with pytest.raises(gate.SupervisedQualificationError):
        _run(h)
    assert h.prepare.call_count == h.execute.call_count == h.forward.call_count == 1
    assert h.terminal.reads == 1 and len(h.store.history()) == 3
