import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from trading_bot.desktop_live import execution
from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.execution import (
    LIVE_ARM_VALUE,
    LiveStateStore,
    execute_plan,
)
from trading_bot.desktop_live.models import (
    LiveExecutionPlan,
    LivePlanState,
    TradabilityObservation,
    parse_order_review,
)


def _plan() -> LiveExecutionPlan:
    review = parse_order_review(
        {
            "data": {
                "result": {
                    "symbol": "SPY",
                    "side": "buy",
                    "type": "market",
                    "dollar_amount": "0.50",
                    "market_hours": "regular_hours",
                    "time_in_force": "gfd",
                    "warnings": [],
                }
            }
        }
    )
    return LiveExecutionPlan.create(
        source_head="a" * 40,
        source_tree="b" * 40,
        policy=TinyLivePolicy(),
        observation_basis="ROBINHOOD_RAW_DAILY_REGULAR_V1",
        target_session="2026-11-02",
        previous_completed_session="2026-10-30",
        signal_values_digest="c" * 64,
        decision="BUY",
        account_fingerprint="d" * 64,
        position_baseline_count=0,
        spy_position_quantity=Decimal("0"),
        order_baseline_count=0,
        current_quote=Decimal("500"),
        risk_outcome="APPROVED",
        approved_quantity=Decimal("0.001"),
        requested_dollars=Decimal("0.50"),
        trade_approval_enabled=False,
        tradability=TradabilityObservation("SPY", True, True, True),
        review=review,
        provider_warning_summary=(),
        state=LivePlanState.READY,
    )


class _FakeTransport:
    def __init__(self):
        self.placed = 0

    def get_accounts(self):
        return {
            "data": {
                "accounts": [{"account_number": "SYNTHETIC", "agentic_allowed": True}]
            }
        }

    def review_equity_order(self, arguments):
        del arguments
        return {
            "data": {
                "result": {
                    "symbol": "SPY",
                    "side": "buy",
                    "type": "market",
                    "dollar_amount": "0.50",
                    "market_hours": "regular_hours",
                    "time_in_force": "gfd",
                    "warnings": [],
                }
            }
        }

    def place_equity_order(self, arguments):
        del arguments
        self.placed += 1
        return {"data": {"id": "provider-order-1"}}


def test_disarmed_plan_stops_before_any_mutation(tmp_path, monkeypatch):
    transport = _FakeTransport()
    monkeypatch.setattr(
        "trading_bot.desktop_live.execution.observe_robinhood_baseline",
        lambda *args, **kwargs: SimpleNamespace(
            account_fingerprint="d" * 64,
            positions=(),
            orders=(),
        ),
    )
    result = execute_plan(
        _plan(),
        transport=transport,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
        state_store=LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl"),
        source_head="a" * 40,
        source_tree="b" * 40,
        arm_token=None,
        plan_digest=None,
    )
    assert result.reason == "LIVE_DISARMED"
    assert transport.placed == 0
    assert result.place_call_count == 0
    assert not result.attempt_consumed
    assert not (tmp_path / "attempt.json").exists()


@pytest.mark.parametrize(
    "provider_state",
    ["partially_filled", "partially-filled", "pending", "open"],
)
def test_nonterminal_post_trade_state_is_consumed_and_never_reconciled(
    tmp_path, monkeypatch, provider_state
):
    transport = _FakeTransport()
    observations = 0

    def observe(*args, **kwargs):
        nonlocal observations
        observations += 1
        if observations == 1:
            return SimpleNamespace(
                account_fingerprint="d" * 64,
                positions=(),
                orders=(),
            )
        return SimpleNamespace(
            account_fingerprint="d" * 64,
            positions=(SimpleNamespace(symbol="SPY", quantity=Decimal("0.001")),),
            orders=(
                SimpleNamespace(
                    order_id="provider-order-1",
                    cumulative_quantity=Decimal("0.001"),
                    state=provider_state,
                ),
            ),
        )

    monkeypatch.setattr(
        "trading_bot.desktop_live.execution.observe_robinhood_baseline", observe
    )
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    plan = _plan()
    result = execute_plan(
        plan,
        transport=transport,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
        state_store=store,
        source_head="a" * 40,
        source_tree="b" * 40,
        arm_token=LIVE_ARM_VALUE,
        plan_digest=plan.plan_sha256,
    )

    assert result.status == "STOPPED"
    assert result.receipt is None
    assert result.reason == "POST_TRADE_RECONCILIATION_BLOCKED"
    assert store.marker.is_file()
    assert result.place_call_count == 1
    assert result.attempt_consumed
    assert result.effect_disposition == "MAY_HAVE_OCCURRED"
    assert transport.placed == 1

    retry = execute_plan(
        plan,
        transport=transport,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
        state_store=store,
        source_head="a" * 40,
        source_tree="b" * 40,
        arm_token=LIVE_ARM_VALUE,
        plan_digest=plan.plan_sha256,
    )

    assert retry.reason == "PRESERVE_CONSUMED_ATTEMPT_NO_RETRY"
    assert retry.place_call_count == 0
    assert retry.attempt_consumed
    assert transport.placed == 1


@pytest.fixture
def ready_execution(tmp_path, monkeypatch):
    """Use only synthetic source, time, transport, environment and state paths."""
    plan = _plan()
    transport = _FakeTransport()
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    now = datetime(2026, 11, 2, 14, 31, tzinfo=UTC)

    def observe(*args, **kwargs):
        if not transport.placed:
            return SimpleNamespace(
                account_fingerprint=plan.account_fingerprint,
                positions=(),
                orders=(),
            )
        return SimpleNamespace(
            positions=(SimpleNamespace(symbol="SPY", quantity=Decimal("0.001")),),
            orders=(
                SimpleNamespace(
                    order_id="provider-order-1",
                    cumulative_quantity=Decimal("0.001"),
                    state="filled",
                ),
            ),
        )

    monkeypatch.setattr(execution, "observe_robinhood_baseline", observe)
    monkeypatch.setattr(execution, "_source_identity", lambda: ("a" * 40, "b" * 40))
    monkeypatch.setattr(execution, "_transport", lambda: transport)
    monkeypatch.setattr(execution, "LIVE_ATTEMPT_MARKER", store.marker)
    monkeypatch.setattr(execution, "LIVE_LIFECYCLE_PATH", store.lifecycle)
    monkeypatch.setattr(execution, "LiveStateStore", lambda *args: store)
    monkeypatch.setattr(execution, "datetime", SimpleNamespace(now=lambda tz: now))
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"plan": plan.sanitized()}), encoding="utf-8")
    # Do not export live arm variables into the actual process environment.
    monkeypatch.setattr(
        execution,
        "os",
        SimpleNamespace(
            fsync=execution.os.fsync,
            environ={
                execution.LIVE_ARM_ENV: LIVE_ARM_VALUE,
                execution.LIVE_PLAN_DIGEST_ENV: plan.plan_sha256,
                execution.LIVE_PLAN_PATH_ENV: str(plan_path),
            },
        ),
    )
    return plan, transport, store


def _assert_consumed_retry(transport, store):
    marker = store.marker.read_bytes()
    placements = transport.placed
    retry = execution.execute()
    assert retry["status"] == "BLOCKED"
    assert retry["reason"] == "PRESERVE_CONSUMED_ATTEMPT_NO_RETRY"
    assert retry["place_call_count"] == 0
    assert retry["attempt_consumed"] is True
    assert retry["automatic_retry"] == "NO_AUTOMATIC_RETRY"
    assert transport.placed == placements
    assert store.marker.read_bytes() == marker


def test_pre_marker_failure_reports_no_placement(ready_execution, monkeypatch):
    _, transport, store = ready_execution

    def fail(**kwargs):
        raise OSError("synthetic marker creation failure")

    monkeypatch.setattr(store, "start_attempt", fail)
    result = execution.execute()
    assert result["status"] == "BLOCKED"
    assert result["place_call_count"] == transport.placed == 0
    assert result["attempt_consumed"] is False
    assert result["effect_disposition"] == "NO_MUTATION"
    assert not store.marker.exists()


@pytest.mark.parametrize("failure", ["marker_write", "initial_lifecycle"])
def test_consumed_pre_placement_failure_has_zero_calls_and_no_retry(
    ready_execution, monkeypatch, failure
):
    _, transport, store = ready_execution
    if failure == "marker_write":

        def fail(**kwargs):
            store.marker.write_text("partial", encoding="utf-8")
            raise OSError("synthetic partial marker write")

        monkeypatch.setattr(store, "start_attempt", fail)
    else:

        def fail(record):
            raise OSError("synthetic initial lifecycle failure")

        monkeypatch.setattr(store, "append", fail)

    result = execution.execute()
    assert result["status"] == "STOPPED"
    assert result["place_call_count"] == transport.placed == 0
    assert result["attempt_consumed"] is True
    assert result["effect_disposition"] == "LIVE_MUTATION_ATTEMPT_STARTED"
    assert result["automatic_retry"] == "NO_AUTOMATIC_RETRY"
    assert result["receipt"] is None
    _assert_consumed_retry(transport, store)


@pytest.mark.parametrize(
    "failure",
    [
        "place",
        "place_and_diagnostic",
        "provider_parse",
        "provider_id_missing",
        "post_observation",
        "post_reconciliation",
        "final_lifecycle",
        "final_lifecycle_and_diagnostic",
    ],
)
def test_post_invocation_failures_preserve_one_call_and_consumed_attempt(
    ready_execution, monkeypatch, failure
):
    _, transport, store = ready_execution
    if failure.startswith("place"):

        def fail_place(arguments):
            transport.placed += 1
            raise RuntimeError("synthetic placement failure; do not expose")

        monkeypatch.setattr(transport, "place_equity_order", fail_place)
    elif failure == "provider_parse":

        def fail_parse(response):
            raise ValueError("synthetic provider parsing failure; do not expose")

        monkeypatch.setattr(execution, "_provider_order_id", fail_parse)
    elif failure == "provider_id_missing":
        monkeypatch.setattr(execution, "_provider_order_id", lambda response: None)
    elif failure == "post_observation":
        observe = execution.observe_robinhood_baseline

        def fail_observe(*args, **kwargs):
            if transport.placed:
                raise ValueError("synthetic observation failure; do not expose")
            return observe(*args, **kwargs)

        monkeypatch.setattr(execution, "observe_robinhood_baseline", fail_observe)
    elif failure == "post_reconciliation":
        observe = execution.observe_robinhood_baseline

        def invalid_post(*args, **kwargs):
            post = observe(*args, **kwargs)
            if transport.placed:
                post.orders[0].cumulative_quantity = None
            return post

        monkeypatch.setattr(execution, "observe_robinhood_baseline", invalid_post)

    if "lifecycle" in failure or "diagnostic" in failure:
        append = store.append

        def fail_append(record):
            if record["status"] == "RECONCILED" or (
                record["status"] == "MAY_HAVE_OCCURRED" and "diagnostic" in failure
            ):
                raise OSError("synthetic lifecycle write failure; do not expose")
            append(record)

        monkeypatch.setattr(store, "append", fail_append)

    result = execution.execute()
    assert result["status"] == "STOPPED"
    assert result["reason"] == result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["place_call_count"] == transport.placed == 1
    assert result["cancel_call_count"] == 0
    assert result["attempt_consumed"] is True
    assert result["automatic_retry"] == "NO_AUTOMATIC_RETRY"
    assert result["receipt"] is None
    assert "synthetic" not in json.dumps(result)
    _assert_consumed_retry(transport, store)


@pytest.mark.parametrize("state", ["filled", "rejected", "canceled", "cancelled"])
def test_terminal_reconciliation_preserves_receipt_and_no_retry(
    ready_execution, monkeypatch, state
):
    _, transport, store = ready_execution
    observe = execution.observe_robinhood_baseline

    def terminal(*args, **kwargs):
        post = observe(*args, **kwargs)
        if transport.placed:
            post.orders[0].state = state
            if state != "filled":
                post.positions = ()
                post.orders[0].cumulative_quantity = Decimal("0")
        return post

    monkeypatch.setattr(execution, "observe_robinhood_baseline", terminal)
    result = execution.execute()
    assert result["status"] == "PASS"
    assert result["reason"] == result["effect_disposition"] == "RECONCILED"
    assert result["place_call_count"] == transport.placed == 1
    assert result["attempt_consumed"] is True
    assert result["receipt"]["state"] == state.upper()
    records = [json.loads(line) for line in store.lifecycle.read_text().splitlines()]
    assert records[-1]["status"] == "RECONCILED"
    assert records[-1]["additional_buy_enabled"] is False
    _assert_consumed_retry(transport, store)


def test_pre_ownership_observation_failure_reports_zero_calls(
    ready_execution, monkeypatch
):
    _, transport, store = ready_execution

    def fail(*args, **kwargs):
        raise ValueError("synthetic pre-placement observation failure")

    monkeypatch.setattr(execution, "observe_robinhood_baseline", fail)
    result = execution.execute()
    assert result["status"] == "BLOCKED"
    assert result["place_call_count"] == transport.placed == 0
    assert result["attempt_consumed"] is False
    assert result["effect_disposition"] == "NO_MUTATION"
    assert not store.marker.exists()
