"""Fake-only D1 history/controller integration using accepted B2/134-C cores."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from tests.market_data.test_alpaca_daily_snapshot import _http_response
from tests.review_paper.test_risk_price_acquisition import _quote
from tests.review_paper.test_store import _review

import trading_bot.robinhood_paper_pipeline as pipeline
from trading_bot.domain import Symbol
from trading_bot.market_data import create_alpaca_daily_snapshot_provider
from trading_bot.review_paper import alpaca_strategy_history as history
from trading_bot.review_paper import armed_session as subject
from trading_bot.review_paper import armed_session_host as host
from trading_bot.review_paper import risk_price_acquisition, supervised_forward_paper
from trading_bot.review_paper.armed_session_store import ArmedSessionStore
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_paper_operator import RobinhoodPaperOperatorEvidence
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

ZONE = ZoneInfo("America/New_York")
AT = datetime(2026, 10, 12, 14, tzinfo=UTC)


def contract(target=date(2026, 10, 12), **changes):
    return host.ProductionStrategyContract(
        target,
        changes.get("head", "a" * 40),
        "b" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
    )


class Clock:
    def __init__(self, at=AT):
        self.at = at
        self.waits = []

    def now(self, *_):
        return self.at

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.at += timedelta(seconds=seconds)


class AlpacaTransport:
    def __init__(self, closes=(10, 10, 9, 12), fault=None):
        self.calls = []
        self.closes = closes
        self.fault = fault

    def execute(self, request, **secrets):
        from urllib.parse import parse_qs, urlsplit

        self.calls.append(request)
        if self.fault == "exception":
            raise RuntimeError("SECRET-ALPACA-KEY https://authorization.invalid")
        params = parse_qs(urlsplit(request.target).query)
        assert params["symbols"] == ["SPY"]
        assert params["adjustment"] == ["raw"]
        assert params["timeframe"] == ["1Day"]
        assert params["feed"] == ["sip"]
        symbol = "QQQ" if self.fault == "wrong_symbol" else "SPY"
        t = params["start"][0]
        if self.fault in {"reordered", "wrong_session"}:
            t = "2026-10-09T04:00:00Z"
        close = self.closes[len(self.calls) - 1]
        bar = {"t": t, "o": close, "h": close, "l": close, "c": close, "v": 100}
        bars = [] if self.fault == "missing" else [bar]
        if self.fault == "duplicate":
            bars += [bar]
        return _http_response(
            json.dumps(
                {
                    "bars": {symbol: bars},
                    "next_page_token": "extra-page"
                    if self.fault == "pagination"
                    else None,
                }
            ).encode()
        )


def provider(transport, clock):
    return create_alpaca_daily_snapshot_provider(
        transport=transport,
        clock=clock.now,
        environment={
            "APCA_API_KEY_ID": "fake-key",
            "APCA_API_SECRET_KEY": "fake-secret",
        },
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (date(2026, 10, 12), [6, 7, 8, 9]),
        (date(2026, 9, 8), [1, 2, 3, 4]),
        (date(2026, 3, 9), [3, 4, 5, 6]),
    ],
)
def test_exact_consecutive_sessions_weekend_holiday_dst(target, expected):
    sessions = history.required_alpaca_history_sessions(contract(target))
    assert [s.session_date.day for s in sessions] == expected
    assert len(sessions) == 4


@pytest.mark.parametrize(
    "target", [date(2026, 10, 11), date(2026, 9, 7), date(2029, 1, 2)]
)
def test_nonpublished_session_rejected(target):
    with pytest.raises(ValueError):
        history.required_alpaca_history_sessions(contract(target))


def test_accepted_history_replays_strict_snapshot_seed_and_raw_requests():
    clock = Clock()
    transport = AlpacaTransport()
    reads = []
    result = history.acquire_current_production_strategy_history_from_alpaca(
        contract(),
        provider(transport, clock),
        requested_at=AT,
        before_read=lambda: reads.append(1),
    )
    assert len(transport.calls) == len(reads) == 4
    assert result.snapshot_verification.passed
    assert len(result.history_seed.seed.bars) == 3
    assert result.history_seed.seed.source.authoritative is False
    assert (
        result.snapshot_verification.snapshot.provider.provider_id
        == "alpaca-market-data"
    )
    assert result.snapshot_verification.snapshot.audit.captured_at == AT


@pytest.mark.parametrize(
    "fault",
    [
        "exception",
        "missing",
        "duplicate",
        "wrong_symbol",
        "wrong_session",
        "reordered",
        "pagination",
    ],
)
def test_bad_history_fails_once_without_retry_or_fallback(fault):
    clock = Clock()
    transport = AlpacaTransport(fault=fault)
    with pytest.raises((RuntimeError, ValueError)):
        history.acquire_current_production_strategy_history_from_alpaca(
            contract(),
            provider(transport, clock),
            requested_at=AT,
            before_read=lambda: None,
        )
    assert len(transport.calls) == 1


@pytest.fixture
def harness(tmp_path, monkeypatch):
    clock = Clock()
    transport = AlpacaTransport()
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    calls = []

    class QuoteTransport:
        def get_equity_quotes(self, arguments):
            calls.append("quote")
            q = _quote("SPY")
            for k in ("venue_ask_time", "venue_bid_time", "venue_last_trade_time"):
                q[k] = clock.at.isoformat()
            return {"data": {"results": [{"quote": q, "close": None}]}}

    adapter = RobinhoodReviewReadAdapter(QuoteTransport())
    monkeypatch.setattr(
        risk_price_acquisition, "datetime", SimpleNamespace(now=clock.now)
    )
    monkeypatch.setattr(
        supervised_forward_paper, "datetime", SimpleNamespace(now=clock.now)
    )
    h = SimpleNamespace(
        clock=clock,
        transport=transport,
        store=store,
        calls=calls,
        source_calls=0,
        fail_source_after=None,
        effect="PASS",
    )

    def admit():
        h.source_calls += 1
        if h.fail_source_after is not None and h.source_calls >= h.fail_source_after:
            raise RuntimeError("source drift SECRET")

    def fake_operator(**kwargs):
        calls.append("operator")
        intent = kwargs["intent"]
        if h.effect == "exception":
            raise RuntimeError("OAUTH-TOKEN-SECRET")
        store.record_market_review(
            intent,
            _review(
                side=intent.side,
                quantity=intent.approved_quantity,
                bid=Decimal("99"),
                ask=Decimal("101"),
                quote_time=clock.at,
            ),
        )
        if h.effect == "ambiguous_fill":
            raise RuntimeError("ambiguous after local fill")
        return RobinhoodPaperOperatorEvidence(
            source_head="a" * 40,
            source_tree="b" * 40,
            status=h.effect,
            phase="complete",
            symbol="SPY",
            side=intent.side.value,
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

    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", fake_operator)
    evaluations = []
    original = MovingAverageCrossoverStrategy.evaluate

    def evaluate(self, *args, **kwargs):
        evaluations.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", evaluate)
    h.evaluations = evaluations
    h.kwargs = dict(
        contract=contract(),
        store=store,
        session_store=ArmedSessionStore(tmp_path / "sessions.sqlite"),
        policy=subject.ArmedSessionPolicy(RiskLimits()),
        expected_branch=host.BRANCH,
        evidence_path=tmp_path / "evidence.json",
        execute_evidence_path=tmp_path / "execution.json",
        arm_interlock=subject.ARM_INTERLOCK,
        clock=clock.now,
        sleeper=clock.sleep,
        admit_source=admit,
        alpaca_provider=lambda: provider(transport, clock),
        quote_adapter=lambda: adapter,
    )
    return h


def run(h, **changes):
    return subject.run_armed_production_paper_session(**(h.kwargs | changes))


def test_ready_delegates_existing_prepare_execute_once_and_records_one_fill(harness):
    h = harness
    result = run(h)
    assert result["status"] == "PAPER_EXECUTED", result
    assert h.calls == ["quote", "operator"]
    assert len(h.evaluations) == 1 and len(h.transport.calls) == 4
    assert len(h.store.history()) == result["paper_mutations"] == 1
    assert result["fill_id"] == str(h.store.history()[0].fill_id)
    assert result["broker_placement_count"] == 0
    assert result["execute_attempts"] == result["prepare_attempts"] == 1
    assert h.clock.waits == []


def test_no_signal_zero_robinhood_and_unchanged_paper_bytes(harness):
    h = harness
    h.transport.closes = (10, 11, 12, 13)
    before = h.store.path.read_bytes()
    result = run(h)
    assert result["status"] == "NO_SIGNAL", result
    assert h.calls == [] and len(h.evaluations) == 1
    assert result["paper_mutations"] == result["prepare_attempts"] == 0
    assert before == h.store.path.read_bytes()


def test_preopen_waits_once_then_continues(harness):
    h = harness
    h.clock.at = AT.replace(hour=12)
    result = run(h)
    assert result["status"] == "PAPER_EXECUTED", result
    assert h.clock.waits == [5700]
    assert result["admitted_at"] == "2026-10-12T13:35:00+00:00"
    assert len(h.evaluations) == 1 and h.calls == ["quote", "operator"]


@pytest.mark.parametrize("at", [AT.replace(hour=20), AT + timedelta(days=1)])
def test_expired_has_no_provider_or_paper_execution(harness, at):
    h = harness
    h.clock.at = at
    assert run(h)["status"] == "SESSION_EXPIRED"
    assert h.transport.calls == h.calls == h.evaluations == []


def test_source_drift_after_wait_blocks_before_robinhood(harness):
    h = harness
    h.clock.at = AT.replace(hour=12)

    def drift(seconds):
        h.clock.sleep(seconds)
        h.fail_source_after = h.source_calls + 1

    assert run(h, sleeper=drift)["status"] == "BLOCKED"
    assert h.calls == [] and len(h.evaluations) == 1


@pytest.mark.parametrize("wake", ["early", "late", "next_date", "twice"])
def test_bad_wake_never_executes_a_second_cycle(harness, wake):
    h = harness
    h.clock.at = AT.replace(hour=12)

    def sleep(seconds):
        if wake == "twice":
            h.clock.sleep(seconds)
            h.clock.sleep(0)
        elif wake == "late":
            h.clock.at = AT.replace(hour=20)
        elif wake == "next_date":
            h.clock.at += timedelta(days=1)

    result = run(h, sleeper=sleep)
    assert result["status"] == (
        "PAPER_EXECUTED"
        if wake == "twice"
        else ("BLOCKED" if wake == "early" else "SESSION_EXPIRED")
    )
    assert h.calls.count("operator") == int(wake == "twice")


def test_risk_rejected_never_executes(harness):
    h = harness
    policy = subject.ArmedSessionPolicy(RiskLimits(allow_buying=False))
    result = run(h, policy=policy)
    assert result["status"] == "RISK_REJECTED", result
    assert h.calls == ["quote"] and not h.store.history()


@pytest.mark.parametrize("effect", ["exception", "FAIL", "ambiguous_fill"])
def test_ambiguous_attempt_stops_and_duplicate_cannot_retry(harness, effect, tmp_path):
    h = harness
    h.effect = effect
    first = run(h)
    assert first["status"] == "BLOCKED", first
    assert first["effect_counts_complete"] is False
    calls = list(h.calls)
    second = run(h, evidence_path=tmp_path / "second.json")
    assert second["status"] == "BLOCKED"
    assert h.calls == calls and len(h.evaluations) == 1
    assert b"SECRET" not in h.kwargs["evidence_path"].read_bytes()


def test_duplicate_launch_completed_has_no_new_effects(harness, tmp_path):
    h = harness
    assert run(h)["status"] == "PAPER_EXECUTED"
    second = run(h, evidence_path=tmp_path / "second.json")
    assert second["status"] == "ALREADY_COMPLETED"
    assert h.calls == ["quote", "operator"] and len(h.store.history()) == 1


def test_changed_contract_cannot_reclaim_same_session(harness, tmp_path):
    h = harness
    assert run(h)["status"] == "PAPER_EXECUTED"
    second = run(
        h, contract=contract(head="c" * 40), evidence_path=tmp_path / "second.json"
    )
    assert second["status"] == "BLOCKED" and len(h.store.history()) == 1


def test_crash_reservation_cannot_be_reclaimed(harness):
    h = harness

    def interrupt():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run(h, alpaca_provider=interrupt)
    assert run(h)["status"] == "BLOCKED" and not h.transport.calls


def test_fake_provider_secret_errors_are_sanitized_and_not_retried(harness):
    h = harness
    h.transport.fault = "exception"
    result = run(h)
    assert result["status"] == "BLOCKED"
    assert len(h.transport.calls) == 1 and not h.calls
    assert b"SECRET" not in h.kwargs["evidence_path"].read_bytes()
    assert len(h.kwargs["evidence_path"].read_bytes()) < 32768


def test_cli_rejects_every_semantic_trading_input_without_effects():
    parser = host.build_parser()
    args = [
        "--expected-head",
        "a" * 40,
        "--expected-tree",
        "b" * 40,
        "--evidence",
        "out.json",
    ]
    for name in (
        "symbol",
        "provider",
        "endpoint",
        "time",
        "target-session",
        "price",
        "side",
        "quantity",
        "long-window",
    ):
        with pytest.raises(ValueError):
            parser.parse_args(args + ["--" + name, "secret-value"])


def test_native_credentials_seam_fails_closed_without_legacy_imports(monkeypatch):
    def missing():
        raise RuntimeError("credential readiness failed")

    monkeypatch.setattr(host, "read_current_product_alpaca_secrets", missing)
    with pytest.raises(RuntimeError, match="readiness failed"):
        host.create_current_product_alpaca_provider()


def test_weak_or_reused_arm_rejected(harness):
    with pytest.raises(ValueError, match="ARM"):
        run(harness, arm_interlock="yes")
    arm = subject._OneSessionArm(harness.kwargs["contract"])
    arm.consume(harness.kwargs["contract"])
    with pytest.raises(ValueError):
        arm.consume(harness.kwargs["contract"])


def test_existing_execution_export_does_not_prevent_completed_replay(harness, tmp_path):
    h = harness
    assert run(h)["status"] == "PAPER_EXECUTED"
    h.kwargs["execute_evidence_path"].write_text("accepted old operator export")
    result = run(h, evidence_path=tmp_path / "again.json")
    assert result["status"] == "ALREADY_COMPLETED"
    assert h.calls == ["quote", "operator"]


def test_concurrent_reservation_is_atomic_without_second_attempt(harness, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from trading_bot.review_paper.armed_session_store import evidence_bytes

    h = harness
    h.transport.closes = (10, 11, 12, 13)
    result = run(h)
    new_store = ArmedSessionStore(tmp_path / "concurrent.sqlite")
    assert new_store.reserve("initialize", result) is None

    def claim():
        try:
            return new_store.reserve("same-session", result) is None
        except sqlite3.OperationalError as exc:
            assert "locked" in str(exc).lower()
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = list(pool.map(lambda _: claim(), range(2)))

    # timeout=0 is deliberately fail-closed: simultaneous contenders may both
    # observe lock contention, but they must never create a second reservation.
    assert sum(winners) <= 1
    with sqlite3.connect(new_store.path) as connection:
        persisted = connection.execute(
            "SELECT COUNT(*) FROM armed_session_v1 WHERE session_key=?",
            ("same-session",),
        ).fetchone()[0]
    assert persisted == sum(winners)
    assert len(evidence_bytes(result)) < 32768


def test_reopened_reserved_state_blocks_across_new_store_object(harness, tmp_path):
    h = harness
    h.transport.fault = "exception"
    assert run(h)["status"] == "BLOCKED"
    restarted = ArmedSessionStore(h.kwargs["session_store"].path)
    assert (
        run(h, session_store=restarted, evidence_path=tmp_path / "restart.json")[
            "status"
        ]
        == "BLOCKED"
    )
    assert len(h.transport.calls) == 1


def test_restart_evidence_rejects_unknown_secret_fields(harness):
    from trading_bot.review_paper.armed_session_store import evidence_bytes

    h = harness
    h.transport.closes = (10, 11, 12, 13)
    result = run(h)
    for changed in (
        result | {"oauth_token": "secret"},
        result | {"status": "SECRET"},
        result | {"historical_sessions": ["authorization-url"]},
    ):
        with pytest.raises((ValueError, TypeError)):
            evidence_bytes(changed)


def test_no_signal_completed_replay_evaluates_zero_additional_times(harness, tmp_path):
    h = harness
    h.transport.closes = (10, 11, 12, 13)
    assert run(h)["status"] == "NO_SIGNAL"
    assert (
        run(h, evidence_path=tmp_path / "again.json")["status"] == "ALREADY_COMPLETED"
    )
    assert len(h.evaluations) == 1 and h.calls == []


def test_expiry_during_prepare_returns_without_execute(harness, monkeypatch):
    h = harness
    original = supervised_forward_paper.acquire_review_paper_risk_price_snapshot

    def acquire(**kwargs):
        h.clock.at = AT.replace(hour=20)
        return original(**kwargs)

    monkeypatch.setattr(
        supervised_forward_paper, "acquire_review_paper_risk_price_snapshot", acquire
    )
    result = run(h)
    assert result["status"] == "SESSION_EXPIRED", result
    assert h.calls == ["quote"] and not h.store.history()


def test_crash_after_execute_fence_never_retries(harness, monkeypatch, tmp_path):
    h = harness

    def interrupt(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(subject, "execute_production_strategy_paper_cycle", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run(h)
    result = run(h, evidence_path=tmp_path / "again.json")
    assert result["status"] == "BLOCKED"
    assert h.calls == ["quote"] and len(h.evaluations) == 1


def test_terminal_publication_failure_preserves_fence_no_retry(
    harness, monkeypatch, tmp_path
):
    h = harness
    original = ArmedSessionStore.publish

    def fail(self, key, before, evidence):
        if evidence["status"] in {"PAPER_EXECUTED", "BLOCKED"}:
            raise OSError("untrusted storage error SECRET")
        return original(self, key, before, evidence)

    monkeypatch.setattr(ArmedSessionStore, "publish", fail)
    with pytest.raises(OSError):
        run(h)
    monkeypatch.setattr(ArmedSessionStore, "publish", original)
    result = run(h, evidence_path=tmp_path / "again.json")
    assert result["status"] == "BLOCKED"
    assert h.calls == ["quote", "operator"] and len(h.store.history()) == 1


def test_quote_only_host_boundary_rejects_historical_and_review_calls():
    transport = SimpleNamespace(get_equity_quotes=lambda _: {})
    boundary = host._QuoteOnly(transport)
    boundary.get_equity_quotes({})
    for name in (
        "get_equity_quotes",
        "get_equity_historicals",
        "review_equity_order",
        "get_equity_orders",
    ):
        with pytest.raises(RuntimeError):
            getattr(boundary, name)({})


def test_authority_registration_and_real_chain():
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch134_armed_paper_authority_check(root) == ()
    spec = runner._checkpoint_specs()[runner.ARCH134_ARMED_PAPER_NAME]
    assert spec.preflight is spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), "feature/robinhood-production-paper-mvp", "push"
        )
        == runner.ARCH134_ARMED_PAPER_NAME
    )


@pytest.mark.parametrize(
    "addition",
    [
        "import trading_bot.runtime.windows_effectful_capture_credentials\n",
        "import trading_bot.runtime.personal_desktop_d10_host\n",
        "import trading_bot.experiments\n",
        "def forbidden(adapter):\n    adapter.get_equity_historicals({})\n",
        "def forbidden(client):\n    client.call_tool('review_equity_order', {})\n",
        "def forbidden(client):\n    client.place_equity_order({})\n",
        "def forbidden(client):\n    client.cancel_equity_order({})\n",
        "def forbidden(client):\n    client.place_options_order({})\n",
        "def forbidden(client):\n    client.place_crypto_order({})\n",
        "def forbidden(scheduler):\n    scheduler.register_task({})\n",
        "def forbidden(strategy):\n    strategy.evaluate({})\n",
    ],
)
def test_authority_ast_rejects_mutations_even_if_pin_refreshed(
    tmp_path, monkeypatch, addition
):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    for relative in runner.ARCH134_ARMED_PAPER_SOURCE_PINS:
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((root / relative).read_text(encoding="utf-8"), encoding="utf-8")
    workflow = tmp_path / ".github/workflows/checkpoint-source-gates.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        (root / ".github/workflows/checkpoint-source-gates.yml").read_text(),
        encoding="utf-8",
    )
    relative = "src/trading_bot/review_paper/armed_session.py"
    dest = tmp_path / relative
    dest.write_text(dest.read_text() + addition, encoding="utf-8")
    pins = dict(runner.ARCH134_ARMED_PAPER_SOURCE_PINS)
    pins[relative] = runner._git_blob_sha1(dest)
    monkeypatch.setattr(runner, "ARCH134_ARMED_PAPER_SOURCE_PINS", pins)
    monkeypatch.setattr(
        runner, "_arch134_production_strategy_live_paper_authority_check", lambda _: ()
    )
    failures = runner._arch134_armed_paper_authority_check(tmp_path)
    assert any("import closure" in f or "forbidden authority" in f for f in failures)


def test_existing_session_fill_without_reservation_blocks_before_history(
    harness, tmp_path
):
    h = harness
    assert run(h)["status"] == "PAPER_EXECUTED"
    result = run(
        h,
        session_store=ArmedSessionStore(tmp_path / "other.sqlite"),
        evidence_path=tmp_path / "other.json",
    )
    assert result["status"] == "BLOCKED"
    assert len(h.transport.calls) == 4 and h.calls == ["quote", "operator"]


def test_isolated_host_import_does_not_load_legacy_authority_graph(tmp_path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    probe = tmp_path / "import_probe.py"
    probe.write_text(
        "import sys\n"
        + "sys.path.insert(0, "
        + repr(str(root / "src"))
        + ")\n"
        + "import trading_bot.review_paper.armed_session_host\n"
        + "assert not any(name.startswith(("
        + "'trading_bot.runtime.windows_effectful_capture', "
        + "'trading_bot.runtime.personal_desktop', 'trading_bot.experiments', "
        + "'trading_bot.optimization')) for name in sys.modules)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(probe)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_source_pin_rejects_even_a_comment_change(tmp_path, monkeypatch):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    for relative in runner.ARCH134_ARMED_PAPER_SOURCE_PINS:
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((root / relative).read_text(encoding="utf-8"), encoding="utf-8")
    dest = tmp_path / "src/trading_bot/review_paper/armed_session.py"
    dest.write_text(dest.read_text() + "\n# drift\n", encoding="utf-8")
    monkeypatch.setattr(
        runner, "_arch134_production_strategy_live_paper_authority_check", lambda _: ()
    )
    assert any(
        "source drift" in f
        for f in runner._arch134_armed_paper_authority_check(tmp_path)
    )
