"""134-B3 verified evidence and single B2 decision composition, using fakes."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from hashlib import sha256
from pathlib import Path

import pytest
from tests.robinhood_mcp.test_historical import make_request, payload_for

from scripts import checkpoint_runner
from trading_bot.review_paper import strategy_market_history as subject
from trading_bot.review_paper.production_strategy_decision import (
    CurrentStrategyDecisionPolicy,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.historical import parse_equity_historicals_response
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)
from trading_bot.strategies.history_seed import (
    StrategyHistorySeedSourceClassification,
    verify_strategy_history_seed,
)
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import ProductionStrategyDecisionStatus


@pytest.fixture
def inputs():
    request = make_request()
    contract = ProductionStrategyContract(
        date(2026, 10, 12),
        "a" * 40,
        "b" * 40,
        request.symbol,
        MovingAverageCrossoverConfig(
            short_window=2, long_window=3, desired_quantity=Decimal("1")
        ),
    )
    history = parse_equity_historicals_response(payload_for(request), request)
    return contract, history


def materialize(inputs):
    contract, history = inputs
    return subject.materialize_production_strategy_history(
        contract,
        history,
        captured_at=history.request.requested_at + timedelta(seconds=1),
    )


def test_verified_canonical_bytes_provenance_and_unchanged_inner_contract(inputs):
    contract, history = inputs
    result = materialize(inputs)
    assert result.snapshot_verification.passed
    assert result.snapshot_verification.snapshot.provider.provider_id == "robinhood"
    assert (
        result.snapshot_verification.snapshot.target_session == history.bars[-1].session
    )
    assert result.history_seed.seed.bars == history.bars[:-1]
    assert (
        result.history_seed.seed.source.classification
        is StrategyHistorySeedSourceClassification.OFFLINE_SEED
    )
    assert result.history_seed.seed.source.authoritative is False
    assert result.history_seed == verify_strategy_history_seed(
        result.history_seed_bytes,
        expected_symbol=contract.symbol,
        target_session=history.bars[-1].session,
        strategy_config=contract.strategy_config,
        calendar=history.request.calendar,
    )
    assert (
        result.snapshot_verification.sha256 == sha256(result.snapshot_bytes).hexdigest()
    )
    outer = json.loads(result.source_evidence_bytes)
    assert outer["arguments"] == history.request.arguments()
    assert outer["response"] == json.loads(history.response_bytes)
    assert outer["tool"] == "get_equity_historicals"
    assert outer["sessions"] == [
        item.session.session_date.isoformat() for item in history.bars
    ]
    with localcontext(Context(prec=2)):
        assert materialize(inputs) == result


def test_acquisition_one_read_no_other_capability(inputs):
    contract, history = inputs
    calls = []

    class Transport:
        def get_equity_historicals(self, arguments):
            calls.append(("history", arguments))
            return payload_for(history.request)

        def __getattr__(self, name):
            raise AssertionError("unexpected tool: " + name)

    def captured():
        calls.append(("capture", None))
        return history.request.requested_at + timedelta(seconds=1)

    result = subject.acquire_production_strategy_history(
        contract,
        RobinhoodReviewReadAdapter(Transport()),
        calendar=history.request.calendar,
        requested_at=history.request.requested_at,
        capture_time=captured,
    )
    assert result == materialize(inputs)
    assert calls == [("history", history.request.arguments()), ("capture", None)]


@pytest.mark.parametrize("invalid", ["target", "window", "adapter", "clock"])
def test_acquisition_rejects_invalid_authority_before_read(inputs, invalid):
    contract, history = inputs

    class Transport:
        def __getattr__(self, name):
            raise AssertionError("provider must not be touched: " + name)

    adapter = RobinhoodReviewReadAdapter(Transport())

    def clock():
        return history.request.requested_at

    if invalid == "target":
        contract = replace(contract, target_session_date=date(2026, 10, 13))
    elif invalid == "window":
        contract = replace(
            contract,
            strategy_config=MovingAverageCrossoverConfig(
                short_window=2, long_window=4097, desired_quantity=Decimal("1")
            ),
        )
    elif invalid == "adapter":
        adapter = object()
    else:
        clock = None
    with pytest.raises((TypeError, ValueError)):
        subject.acquire_production_strategy_history(
            contract,
            adapter,
            calendar=history.request.calendar,
            requested_at=history.request.requested_at,
            capture_time=clock,
        )


def test_provider_failure_is_not_retried_or_filled(inputs):
    contract, history = inputs
    calls = []

    class Transport:
        def get_equity_historicals(self, arguments):
            calls.append(arguments)
            raise RuntimeError("provider unavailable")

        def __getattr__(self, name):
            raise AssertionError("fallback forbidden")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        subject.acquire_production_strategy_history(
            contract,
            RobinhoodReviewReadAdapter(Transport()),
            calendar=history.request.calendar,
            requested_at=history.request.requested_at,
            capture_time=lambda: pytest.fail("failed provider must not reach capture"),
        )
    assert calls == [history.request.arguments()]


@pytest.mark.parametrize(
    "captured_at",
    [
        datetime(2026, 10, 12, 12, tzinfo=UTC),
        datetime(2026, 10, 13, 13, tzinfo=UTC),
        datetime(2026, 10, 12, 13),
    ],
)
def test_bad_capture_time_fails(inputs, captured_at):
    contract, history = inputs
    with pytest.raises(ValueError):
        subject.materialize_production_strategy_history(
            contract, history, captured_at=captured_at
        )


def test_altered_parsed_bars_fail_replay(inputs):
    contract, history = inputs
    history = replace(history, bars=history.bars[::-1])
    with pytest.raises(ValueError, match="retained response"):
        subject.materialize_production_strategy_history(
            contract, history, captured_at=history.request.requested_at
        )


@pytest.mark.parametrize("no_signal", [False, True])
def test_b2_composition_evaluates_once_and_does_not_mutate_paper(
    inputs, tmp_path, monkeypatch, no_signal
):
    contract, history = inputs
    if no_signal:
        payload = payload_for(history.request)
        for bar in payload["data"]["results"][0]["bars"]:
            for key in ("open_price", "high_price", "low_price", "close_price"):
                bar[key] = "10"
        history = parse_equity_historicals_response(payload, history.request)
    evidence = materialize((contract, history))
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("1000"))
    before = store.path.read_bytes(), store.history()
    evaluations, proposals = [], []
    original = MovingAverageCrossoverStrategy.evaluate

    def evaluate(self, context):
        evaluations.append(context)
        result = original(self, context)
        proposals.append(result)
        return result

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", evaluate)

    def forbidden(*args, **kwargs):
        pytest.fail("paper mutation is forbidden")

    monkeypatch.setattr(ReviewPaperStore, "record_market_review", forbidden)
    result = subject.build_production_strategy_decision_from_history(
        contract,
        store,
        evidence=evidence,
        planning_at=evidence.captured_at + timedelta(seconds=1),
        caller_idempotency_key="b3-cycle-1",
        policy=CurrentStrategyDecisionPolicy(timedelta(minutes=10)),
    )
    assert len(evaluations) == 1
    assert result.proposal is proposals[0]
    assert result.status is (
        ProductionStrategyDecisionStatus.NO_SIGNAL
        if no_signal
        else ProductionStrategyDecisionStatus.TRADE_PROPOSAL
    )
    assert (store.path.read_bytes(), store.history()) == before


@pytest.mark.parametrize(
    "field", ["source_evidence_bytes", "snapshot_bytes", "history_seed_bytes"]
)
def test_corrupt_evidence_cannot_reach_b2(inputs, field, monkeypatch):
    evidence = replace(materialize(inputs), **{field: b"corrupt"})
    monkeypatch.setattr(
        subject,
        "build_current_production_strategy_decision",
        lambda *args, **kwargs: pytest.fail("must reject before B2"),
    )
    with pytest.raises(ValueError, match="replay exactly"):
        subject.build_production_strategy_decision_from_history(
            inputs[0],
            object(),
            evidence=evidence,
            planning_at=evidence.captured_at,
            caller_idempotency_key="b3",
            policy=CurrentStrategyDecisionPolicy(timedelta(minutes=10)),
        )


def test_b3_registered_source_only_and_exact_authority():
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    spec = checkpoint_runner._checkpoint_specs()[
        "arch134-production-strategy-live-paper"
    ]
    assert spec.preflight is None and spec.execute is None
    assert {
        "tests/robinhood_mcp/test_historical.py",
        "tests/review_paper/test_strategy_market_history.py",
    } <= set(spec.tests)
    assert checkpoint_runner._arch134_market_history_authority_check(root) == ()


def test_provenance_does_not_rewrite_inner_domain_identities(inputs):
    contract, history = inputs
    original = materialize(inputs)
    payload = json.loads(history.response_bytes)
    payload["guide"] = "Different retained provider disclosure."
    changed = parse_equity_historicals_response(payload, history.request)
    result = materialize((contract, changed))
    assert result.history_seed_bytes == original.history_seed_bytes
    assert (
        result.snapshot_verification.snapshot.snapshot_id
        == original.snapshot_verification.snapshot.snapshot_id
    )
    assert result.snapshot_bytes != original.snapshot_bytes
    assert (
        result.snapshot_verification.snapshot.audit.source_payload.sha256
        == sha256(changed.response_bytes).hexdigest()
    )


@pytest.mark.parametrize(
    "path,addition",
    [
        ("src/trading_bot/robinhood_mcp/historical.py", "import socket"),
        (
            "src/trading_bot/review_paper/strategy_market_history.py",
            "def call_tool(): pass",
        ),
        (
            "src/trading_bot/review_paper/strategy_market_history.py",
            "def unsafe(): return ReviewPaperStore('other')",
        ),
        (
            "src/trading_bot/review_paper/strategy_market_history.py",
            "import trading_bot.runtime.windows_authority",
        ),
    ],
)
def test_b3_authority_rejects_extra_capabilities(tmp_path, path, addition):
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    files = (
        *checkpoint_runner.ARCH134_MARKET_HISTORY_SOURCE_PINS,
        "src/trading_bot/robinhood_mcp/adapter.py",
        "src/trading_bot/robinhood_mcp/sdk_transport.py",
    )
    for relative in files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    assert checkpoint_runner._arch134_market_history_authority_check(tmp_path) == ()
    target = tmp_path / path
    target.write_text(
        target.read_text(encoding="utf-8") + "\n" + addition + "\n", encoding="utf-8"
    )
    assert checkpoint_runner._arch134_market_history_authority_check(tmp_path)
