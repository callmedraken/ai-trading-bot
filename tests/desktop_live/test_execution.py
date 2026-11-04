import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5

import pytest

from scripts import arch147_p6_tiny_live_source as p6_source
from trading_bot.desktop_live import execution
from trading_bot.desktop_live import kill_operator as kill
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
from trading_bot.desktop_live.ownership import (
    OWNERSHIP_SCHEMA,
    OwnedOrderBinding,
    load_binding,
    local_order_id,
)
from trading_bot.desktop_live.preflight import review_order_arguments
from trading_bot.desktop_paper.robinhood_read import parse_order, resolve_account


def _plan() -> LiveExecutionPlan:
    review = parse_order_review(
        {
            "data": {
                "symbol": "SPY",
                "side": "buy",
                "type": "market",
                "dollar_amount": "0.50",
                "order_checks": {},
            }
        },
        expected=review_order_arguments(Decimal("0.50"), "SYNTHETIC"),
    )
    return LiveExecutionPlan.create(
        source_head="a" * 40,
        source_tree="b" * 40,
        policy=TinyLivePolicy(),
        observation_basis="ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1",
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
        self.canceled = 0
        self.review_arguments = []
        self.placement_arguments = []

    def get_accounts(self):
        return {
            "data": {
                "accounts": [{"account_number": "SYNTHETIC", "agentic_allowed": True}]
            }
        }

    def review_equity_order(self, arguments):
        self.review_arguments.append(dict(arguments))
        return {
            "data": {
                "symbol": "SPY",
                "side": "buy",
                "type": "market",
                "dollar_amount": "0.50",
                "order_checks": {},
            }
        }

    def place_equity_order(self, arguments):
        self.placement_arguments.append(dict(arguments))
        self.placed += 1
        return {"data": {"approval": {}, "order": {"id": "provider-order-1"}}}

    def cancel_equity_order(self, arguments):
        self.canceled += 1
        raise AssertionError("placement admission cannot cancel")


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
    monkeypatch.setattr(execution, "create_live_transport", lambda: transport)
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
        "binding_write",
        "binding_conflict",
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
    elif failure == "binding_write":

        def fail_binding(*args):
            raise OSError("synthetic secret binding write failure")

        monkeypatch.setattr(store, "bind_order", fail_binding)
    elif failure == "binding_conflict":
        place = transport.place_equity_order

        def conflicting_place(arguments):
            store.bind_order(_plan(), "another-order")
            return place(arguments)

        monkeypatch.setattr(transport, "place_equity_order", conflicting_place)
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


class _CancelTransport(_FakeTransport):
    def __init__(self, *, raises=False):
        super().__init__()
        self.cancel_arguments = []
        self.raises = raises

    def cancel_equity_order(self, arguments):
        self.cancel_arguments.append(arguments)
        if self.raises:
            raise RuntimeError("SYNTHETIC_RAW_PROVIDER_SECRET must not escape")
        return {"data": {"status": "cancel_requested"}}


def _kill(plan, transport, store, *, latched=True, order_id="owned-provider-order-1"):
    if order_id and not store.ownership_path.exists():
        store.bind_order(plan, order_id)
    return execution.kill_owned_order(
        plan=plan,
        transport=transport,
        account_number="SYNTHETIC",
        kill_latched=latched,
        state_store=store,
    )


def _assert_cancel_retry_blocked(plan, transport, store):
    marker = store.marker.with_name("cancel-attempt.json")
    before = marker.read_bytes()
    calls = list(transport.cancel_arguments)
    retry = _kill(plan, transport, store)
    assert retry.status == "BLOCKED"
    assert retry.reason == "PRESERVE_CONSUMED_CANCEL_NO_RETRY"
    assert retry.attempt_consumed
    assert retry.effect_disposition == "MAY_HAVE_OCCURRED"
    assert retry.receipt is None
    assert retry.place_call_count == retry.cancel_call_count == 0
    assert transport.placed == 0
    assert transport.cancel_arguments == calls
    assert marker.read_bytes() == before


@pytest.mark.parametrize("raises", [False, True])
def test_exact_owned_cancel_is_consumed_without_claiming_terminal_state(
    tmp_path, raises
):
    plan = _plan()
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    transport = _CancelTransport(raises=raises)

    result = _kill(plan, transport, store)

    assert result.status == ("STOPPED" if raises else "PASS")
    assert result.reason == (
        "MAY_HAVE_OCCURRED" if raises else "EXACT_OWNED_ORDER_CANCEL_REQUESTED"
    )
    assert result.effect_disposition == "MAY_HAVE_OCCURRED"
    assert result.attempt_consumed
    assert result.receipt is None
    assert result.place_call_count == transport.placed == 0
    assert result.cancel_call_count == len(transport.cancel_arguments) == 1
    assert transport.cancel_arguments == [
        {"account_number": "SYNTHETIC", "order_id": "owned-provider-order-1"}
    ]
    assert "SYNTHETIC_RAW_PROVIDER_SECRET" not in repr(result)
    marker = store.marker.with_name("cancel-attempt.json")
    assert json.loads(marker.read_text())["automatic_retry"] == "NO_AUTOMATIC_RETRY"
    assert not store.marker.exists()
    _assert_cancel_retry_blocked(plan, transport, store)


def test_existing_cancel_marker_preserves_uncertainty_with_zero_new_calls(tmp_path):
    plan = _plan()
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    transport = _CancelTransport()
    store.marker.with_name("cancel-attempt.json").write_text("preserved partial marker")
    _assert_cancel_retry_blocked(plan, transport, store)
    assert transport.cancel_arguments == []


@pytest.mark.parametrize(
    ("latched", "order_id", "reason"),
    [
        (False, "owned-provider-order-1", "KILL_NOT_LATCHED"),
        (True, "", "ORDER_OWNERSHIP_AMBIGUOUS"),
    ],
)
def test_kill_before_cancel_authority_is_zero_effect(
    tmp_path, latched, order_id, reason
):
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    transport = _CancelTransport()
    result = _kill(_plan(), transport, store, latched=latched, order_id=order_id)
    assert result.reason == reason
    assert result.status == "BLOCKED"
    assert result.effect_disposition == "NO_MUTATION"
    assert not result.attempt_consumed
    assert result.receipt is None
    assert result.cancel_call_count == result.place_call_count == transport.placed == 0
    assert transport.cancel_arguments == []
    assert not store.marker.with_name("cancel-attempt.json").exists()


@pytest.mark.parametrize("failure", ["before_marker", "partial_marker", "marker_race"])
def test_cancel_marker_failures_never_invoke_transport(tmp_path, monkeypatch, failure):
    plan = _plan()
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    transport = _CancelTransport()
    marker = store.marker.with_name("cancel-attempt.json")

    def fail_start(self, **kwargs):
        if failure != "before_marker":
            self.marker.write_text("preserved partial marker")
        if failure == "marker_race":
            raise FileExistsError("synthetic competing cancel attempt")
        raise OSError("SYNTHETIC_RAW_PROVIDER_SECRET marker failure")

    monkeypatch.setattr(LiveStateStore, "start_attempt", fail_start)
    result = _kill(plan, transport, store)
    assert result.place_call_count == result.cancel_call_count == transport.placed == 0
    assert transport.cancel_arguments == []
    assert result.receipt is None
    assert "SYNTHETIC_RAW_PROVIDER_SECRET" not in repr(result)
    assert result.attempt_consumed == (failure != "before_marker")
    assert (
        result.effect_disposition
        == {
            "before_marker": "NO_MUTATION",
            "partial_marker": "LIVE_MUTATION_ATTEMPT_STARTED",
            "marker_race": "MAY_HAVE_OCCURRED",
        }[failure]
    )
    if failure == "before_marker":
        assert result.status == "BLOCKED"
        assert not marker.exists()
    else:
        assert result.status == ("BLOCKED" if failure == "marker_race" else "STOPPED")
        _assert_cancel_retry_blocked(plan, transport, store)


@pytest.fixture
def ready_kill(tmp_path, monkeypatch):
    transport = _CancelTransport()
    original = _plan()
    material = {
        name: getattr(original, name)
        for name in original.__dataclass_fields__
        if name != "plan_sha256"
    }
    plan = LiveExecutionPlan.create(
        **(
            material
            | {
                "account_fingerprint": resolve_account(
                    transport.get_accounts()
                ).fingerprint
            }
        )
    )
    store = LiveStateStore(
        tmp_path / "state/attempt.json", tmp_path / "state/life.jsonl"
    )
    store.bind_order(plan, "owned-provider-order-1")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"plan": plan.sanitized()}), encoding="utf-8")
    evidence = tmp_path / "evidence"
    events = []
    observations = []

    def snapshot(
        state="open",
        fill="0",
        position=None,
        order_id="owned-provider-order-1",
        **changes,
    ):
        order = parse_order(
            {
                "id": order_id,
                "symbol": "SPY",
                "side": "buy",
                "state": state,
                "quantity": None,
                "cumulative_quantity": fill,
                "created_at": "2026-11-02T14:31:00+00:00",
                "placed_agent": "agentic",
                **changes,
            }
        )
        return SimpleNamespace(
            account_fingerprint=plan.account_fingerprint,
            orders=(order,),
            positions=(
                SimpleNamespace(symbol="SPY", quantity=Decimal(position or fill)),
            ),
        )

    observations.extend([snapshot(), snapshot("canceled")])

    def admit(*args):
        events.append("admission")
        return plan.source_head, plan.source_tree

    def construct():
        events.append("transport")
        return transport

    def observe(*args, **kwargs):
        events.append("observation")
        item = observations.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(p6_source, "require_kill_source", admit)
    monkeypatch.setattr(kill, "_state_store", lambda: store)
    monkeypatch.setattr(kill, "create_live_transport", construct)
    monkeypatch.setattr(kill, "observe_robinhood_baseline", observe)
    # Never export either kill or BUY arms into the real process environment.
    monkeypatch.setattr(
        kill,
        "os",
        SimpleNamespace(
            environ={kill.KILL_ARM_ENV: kill.KILL_ARM_VALUE},
            fsync=kill.os.fsync,
        ),
    )

    def run(destination=None, digest=None):
        return kill.run_operator(
            repo_root=Path(__file__).resolve().parents[2],
            plan_path=plan_path,
            plan_digest=plan.plan_sha256 if digest is None else digest,
            evidence_directory=evidence if destination is None else destination,
        )

    return SimpleNamespace(
        plan=plan,
        store=store,
        transport=transport,
        run=run,
        events=events,
        observations=observations,
        snapshot=snapshot,
        evidence=evidence,
        plan_path=plan_path,
    )


@pytest.mark.parametrize(
    "failure",
    [
        "source",
        "arm",
        "missing_binding",
        "digest",
        "binding_digest",
        "local_order",
        "provider_id",
        "schema",
        "plan_tamper",
        "plan_source",
        "not_ready",
        "evidence_exists",
    ],
)
def test_kill_local_failures_precede_provider_construction(
    ready_kill, monkeypatch, failure
):
    f = ready_kill
    if failure == "source":

        def reject(*args):
            raise RuntimeError("SYNTHETIC_RAW_PROVIDER_SECRET")

        monkeypatch.setattr(p6_source, "require_kill_source", reject)
    elif failure == "arm":
        kill.os.environ.clear()
    elif failure == "missing_binding":
        f.store.ownership_path.unlink()
    elif failure in {"binding_digest", "local_order", "provider_id", "schema"}:
        body = json.loads(f.store.ownership_path.read_text())
        field, value = {
            "binding_digest": ("plan_sha256", "e" * 64),
            "local_order": ("local_order_id", "e" * 64),
            "provider_id": ("provider_order_id", "bad id\nsecret"),
            "schema": ("schema", "other"),
        }[failure]
        body[field] = value
        f.store.ownership_path.write_text(json.dumps(body))
    elif failure in {"plan_tamper", "plan_source", "not_ready"}:
        raw = json.loads(f.plan_path.read_text())
        raw["plan"][
            {
                "plan_tamper": "requested_dollar_amount",
                "plan_source": "source_head",
                "not_ready": "plan_state",
            }[failure]
        ] = {"plan_tamper": "9.00", "plan_source": "e" * 40, "not_ready": "BLOCKED"}[
            failure
        ]
        f.plan_path.write_text(json.dumps(raw))
    elif failure == "evidence_exists":
        f.evidence.mkdir()
    result = f.run(digest="e" * 64 if failure == "digest" else None)
    assert result["status"] == "BLOCKED"
    assert "transport" not in f.events
    assert f.transport.cancel_arguments == []
    assert f.transport.placed == result["cancel_call_count"] == 0
    assert "SYNTHETIC" not in json.dumps(result)


def test_kill_independent_arm_and_terminal_cancel_evidence(ready_kill):
    f = ready_kill
    assert execution.LIVE_ARM_ENV not in kill.os.environ
    result = f.run()
    assert f.events == ["admission", "transport", "observation", "observation"]
    assert result["classification"] == "TERMINAL_CANCELED"
    assert result["effect_disposition"] == "RECONCILED"
    assert result["cancel_call_count"] == len(f.transport.cancel_arguments) == 1
    assert result["attempt_consumed"] is True
    assert result["additional_buy_enabled"] is False
    assert result["automatic_retry"] == "NO_AUTOMATIC_RETRY"
    saved = json.loads((f.evidence / "report.json").read_text())
    assert saved == result
    assert "owned-provider-order-1" not in json.dumps(saved)
    assert "SYNTHETIC" not in json.dumps(saved)
    assert (
        saved["provider_order_sha256"]
        == load_binding(f.store.ownership_path, f.plan).provider_order_sha256
    )


@pytest.mark.parametrize(
    "state,fill,classification",
    [
        ("filled", "0.001", "TERMINAL_FILLED"),
        ("canceled", "0", "TERMINAL_CANCELED"),
        ("cancelled", "0", "TERMINAL_CANCELED"),
        ("rejected", "0", "TERMINAL_REJECTED"),
        ("canceled", "0.001", "TERMINAL_CANCELED_REMAINDER"),
    ],
)
def test_kill_already_terminal_never_cancels_or_liquidates(
    ready_kill, state, fill, classification
):
    f = ready_kill
    f.observations[:] = [f.snapshot(state, fill)]
    result = f.run()
    assert result["classification"] == classification
    assert result["cancel_call_count"] == f.transport.placed == 0
    assert f.transport.cancel_arguments == []
    assert not f.store.marker.with_name("cancel-attempt.json").exists()
    assert result["spy_position_quantity"] == fill


@pytest.mark.parametrize(
    "change",
    [
        "account",
        "snapshot_account",
        "absent",
        "similar",
        "symbol",
        "side",
        "session",
        "unknown_state",
    ],
)
def test_kill_requires_exact_order_and_corroboration(ready_kill, monkeypatch, change):
    f = ready_kill
    if change == "account":
        monkeypatch.setattr(
            f.transport,
            "get_accounts",
            lambda: {
                "data": {
                    "accounts": [{"account_number": "OTHER", "agentic_allowed": True}]
                }
            },
        )
    elif change == "snapshot_account":
        f.observations[0].account_fingerprint = "e" * 64
    elif change in {"absent", "similar"}:
        f.observations[0].orders = (
            ()
            if change == "absent"
            else f.snapshot(order_id="another-similar-SPY").orders
        )
    elif change == "session":
        f.observations[0] = f.snapshot(created_at="2026-10-30T14:31:00+00:00")
    else:
        field, value = {
            "symbol": ("symbol", "QQQ"),
            "side": ("side", "sell"),
            "unknown_state": ("state", "provider-secret-state"),
        }[change]
        f.observations[0] = f.snapshot(**{field: value})
    result = f.run()
    assert result["status"] == "BLOCKED"
    assert result["cancel_call_count"] == 0
    assert f.transport.cancel_arguments == []
    assert "provider-secret-state" not in json.dumps(result)


def test_similar_spy_order_does_not_replace_exact_target(ready_kill):
    f = ready_kill
    f.observations[0].orders += f.snapshot(order_id="another-similar-SPY").orders
    assert f.run()["classification"] == "TERMINAL_CANCELED"
    assert f.transport.cancel_arguments == [
        {"account_number": "SYNTHETIC", "order_id": "owned-provider-order-1"}
    ]


@pytest.mark.parametrize(
    "state,fill,position,classification",
    [
        ("canceled", "0.001", "0.001", "TERMINAL_CANCELED_REMAINDER"),
        ("cancelled", "0.001", "0.001", "TERMINAL_CANCELED_REMAINDER"),
        ("filled", "0.002", "0.002", "TERMINAL_FILLED"),
        ("canceled", "0.001", "0", "UNRECONCILED"),
        ("canceled", "0", "0", "UNRECONCILED"),
        ("rejected", "0.001", "0.001", "UNRECONCILED"),
    ],
)
def test_post_cancel_fill_and_position_consistency(
    ready_kill, state, fill, position, classification
):
    f = ready_kill
    f.observations[:] = [
        f.snapshot("partially_filled", "0.001"),
        f.snapshot(state, fill, position),
    ]
    result = f.run()
    assert result["classification"] == classification
    assert result["cancel_call_count"] == len(f.transport.cancel_arguments) == 1
    assert result["spy_position_quantity"] == position
    assert result["additional_buy_enabled"] is False
    assert result["effect_disposition"] == (
        "MAY_HAVE_OCCURRED" if classification == "UNRECONCILED" else "RECONCILED"
    )


@pytest.mark.parametrize(
    "failure",
    [
        "open",
        "pending",
        "partially_filled",
        "missing",
        "parse",
        "cancel",
        "post_account",
    ],
)
def test_cancel_uncertainty_is_consumed_sanitized_and_never_retried(
    ready_kill, failure
):
    f = ready_kill
    if failure == "cancel":
        f.transport.raises = True
    elif failure == "parse":
        f.observations[1] = ValueError("SYNTHETIC_RAW_PROVIDER_SECRET")
    elif failure == "missing":
        f.observations[1].orders = ()
    elif failure == "post_account":
        f.observations[1].account_fingerprint = "e" * 64
    else:
        f.observations[1] = f.snapshot(failure)
    result = f.run()
    assert result["status"] == "STOPPED"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["cancel_call_count"] == len(f.transport.cancel_arguments) == 1
    assert result["attempt_consumed"] is True
    assert result["automatic_retry"] == "NO_AUTOMATIC_RETRY"
    assert "SYNTHETIC_RAW_PROVIDER_SECRET" not in json.dumps(result)
    assert (
        "SYNTHETIC_RAW_PROVIDER_SECRET" not in (f.evidence / "report.json").read_text()
    )
    marker = f.store.marker.with_name("cancel-attempt.json").read_bytes()
    f.observations[:] = [f.snapshot()]
    retry = f.run(f.evidence.with_name("recovery"))
    assert retry["cancel_call_count"] == 0
    assert retry["attempt_consumed"] is True
    assert len(f.transport.cancel_arguments) == 1
    assert f.store.marker.with_name("cancel-attempt.json").read_bytes() == marker


@pytest.mark.parametrize(
    "state,classification",
    [
        ("open", "UNRECONCILED"),
        ("filled", "TERMINAL_FILLED"),
        ("canceled", "TERMINAL_CANCELED_REMAINDER"),
    ],
)
def test_existing_cancel_marker_allows_terminal_observation_only(
    ready_kill, state, classification
):
    f = ready_kill
    marker = f.store.marker.with_name("cancel-attempt.json")
    marker.write_text("preserved partial consumed marker")
    before = marker.read_bytes()
    f.observations[:] = [f.snapshot(state, "0.001")]
    result = f.run()
    assert result["classification"] == classification
    assert result["cancel_call_count"] == len(f.transport.cancel_arguments) == 0
    assert result["attempt_consumed"] is True
    assert marker.read_bytes() == before


def test_operator_has_no_arbitrary_provider_order_argument(ready_kill):
    f = ready_kill
    with pytest.raises(SystemExit):
        kill.main(
            [
                "--plan",
                str(f.plan_path),
                "--plan-sha256",
                f.plan.plan_sha256,
                "--evidence-dir",
                str(f.evidence),
                "--order-id",
                "arbitrary",
            ]
        )
    assert f.events == []
    with pytest.raises(TypeError):
        execution.kill_owned_order(
            plan=f.plan,
            transport=f.transport,
            account_number="SYNTHETIC",
            provider_order_id="arbitrary",
            kill_latched=True,
            state_store=f.store,
        )
    # A fabricated in-memory binding also cannot select another target.
    fake = OwnedOrderBinding(
        OWNERSHIP_SCHEMA,
        f.plan.plan_sha256,
        execution._local_order_id(f.plan),
        "arbitrary",
    )
    result = kill.observe_and_kill(
        f.plan,
        binding=fake,
        transport=f.transport,
        state_store=f.store,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
    )
    assert result.cancel_call_count == 0
    assert f.events == []


@pytest.mark.parametrize(
    "provider_id", ["owned-provider-order-1", "different-provider-order"]
)
def test_ownership_is_create_only_even_when_existing_binding_matches(
    ready_kill, provider_id
):
    f = ready_kill
    before = f.store.ownership_path.read_bytes()
    with pytest.raises(FileExistsError):
        f.store.bind_order(f.plan, provider_id)
    assert f.store.ownership_path.read_bytes() == before


def test_placement_persists_exact_binding_before_post_observation(
    ready_execution, monkeypatch
):
    plan, transport, store = ready_execution
    observe = execution.observe_robinhood_baseline

    def assert_binding(*args, **kwargs):
        if transport.placed:
            binding = load_binding(store.ownership_path, plan)
            assert binding.provider_order_id == "provider-order-1"
            assert binding.local_order_id == execution._local_order_id(plan)
        return observe(*args, **kwargs)

    monkeypatch.setattr(execution, "observe_robinhood_baseline", assert_binding)
    result = execution.execute()
    assert result["status"] == "PASS"
    assert result["place_call_count"] == transport.placed == 1
    assert load_binding(store.ownership_path, plan).schema == OWNERSHIP_SCHEMA


@pytest.mark.parametrize(
    "bad", ["", " id", "id\nsecret", "https://provider/order", 12, "x" * 129]
)
def test_malformed_placement_provider_id_never_creates_binding(
    ready_execution, monkeypatch, bad
):
    plan, transport, store = ready_execution

    def place(arguments):
        transport.placed += 1
        return {"data": {"id": bad}}

    monkeypatch.setattr(transport, "place_equity_order", place)
    result = execution.execute()
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["place_call_count"] == 1
    assert not store.ownership_path.exists()
    _assert_consumed_retry(transport, store)


def test_kill_only_fake_rejects_all_placement_review_sell_capabilities(
    ready_kill, monkeypatch
):
    f = ready_kill
    forbidden = []

    class KillOnly:
        def get_accounts(self):
            return f.transport.get_accounts()

        def cancel_equity_order(self, arguments):
            return f.transport.cancel_equity_order(arguments)

        def __getattr__(self, name):
            forbidden.append(name)
            raise AssertionError("Unreviewed capability accessed")

    monkeypatch.setattr(kill, "create_live_transport", KillOnly)
    result = f.run()
    assert result["classification"] == "TERMINAL_CANCELED"
    assert forbidden == []
    assert result["place_call_count"] == 0


def test_binding_conflict_after_placement_is_preserved(ready_execution, monkeypatch):
    plan, transport, store = ready_execution
    place = transport.place_equity_order
    preserved = None

    def race(arguments):
        nonlocal preserved
        store.bind_order(plan, "competing-provider-order")
        preserved = store.ownership_path.read_bytes()
        return place(arguments)

    monkeypatch.setattr(transport, "place_equity_order", race)
    result = execution.execute()
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["place_call_count"] == transport.placed == 1
    assert store.ownership_path.read_bytes() == preserved
    _assert_consumed_retry(transport, store)


def test_existing_ownership_blocks_new_placement_before_provider(ready_execution):
    plan, transport, store = ready_execution
    store.bind_order(plan, "preserved-provider-order")
    result = execution.execute()
    assert result["reason"] == "EXISTING_OWNERSHIP_BINDING_NO_PLACEMENT"
    assert result["place_call_count"] == transport.placed == 0


def test_kill_evidence_failure_preserves_consumed_call_facts(ready_kill, monkeypatch):
    f = ready_kill
    write = kill._write_create_only

    def fail_report(path, body):
        if path.name == "report.json":
            raise OSError("SYNTHETIC_RAW_PROVIDER_SECRET")
        write(path, body)

    monkeypatch.setattr(kill, "_write_create_only", fail_report)
    result = f.run()
    assert result["status"] == "STOPPED"
    assert result["cancel_call_count"] == len(f.transport.cancel_arguments) == 1
    assert result["attempt_consumed"] is True
    assert result["evidence_persistence"] == "FAILED"
    assert "SYNTHETIC_RAW_PROVIDER_SECRET" not in json.dumps(result)


def test_evidence_reservation_failure_blocks_transport(ready_kill, monkeypatch):
    f = ready_kill

    def fail(*args):
        raise OSError("SYNTHETIC_RAW_PROVIDER_SECRET")

    monkeypatch.setattr(kill, "_write_create_only", fail)
    assert f.run()["status"] == "BLOCKED"
    assert "transport" not in f.events


def test_partial_binding_is_never_repaired(ready_execution, monkeypatch):
    from trading_bot.desktop_live import ownership

    plan, transport, store = ready_execution

    def fail_fsync(*args):
        raise OSError("SYNTHETIC_RAW_PROVIDER_SECRET")

    monkeypatch.setattr(ownership, "os", SimpleNamespace(fsync=fail_fsync))
    result = execution.execute()
    assert result["place_call_count"] == transport.placed == 1
    assert result["attempt_consumed"] is True
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert store.ownership_path.exists()
    before = store.ownership_path.read_bytes()
    _assert_consumed_retry(transport, store)
    assert store.ownership_path.read_bytes() == before


def test_binding_change_during_observation_cannot_retarget_cancel(
    ready_kill, monkeypatch
):
    f = ready_kill
    observe = kill.observe_robinhood_baseline

    def change_binding(*args, **kwargs):
        snapshot = observe(*args, **kwargs)
        raw = json.loads(f.store.ownership_path.read_text())
        raw["provider_order_id"] = "another-similar-SPY"
        f.store.ownership_path.write_text(json.dumps(raw))
        return snapshot

    monkeypatch.setattr(kill, "observe_robinhood_baseline", change_binding)
    result = f.run()
    assert result["reason"] == "ORDER_OWNERSHIP_CHANGED"
    assert result["cancel_call_count"] == len(f.transport.cancel_arguments) == 0
    assert not f.store.marker.with_name("cancel-attempt.json").exists()


def test_filled_quantity_must_match_known_total_order_quantity(ready_kill):
    f = ready_kill
    f.observations[:] = [f.snapshot("filled", "0.001", quantity="0.002")]
    result = f.run()
    assert result["status"] == "STOPPED"
    assert result["post_cancel_state"] == "FILLED"
    assert result["classification"] == "UNRECONCILED"
    assert result["cancel_call_count"] == 0


@pytest.mark.parametrize(
    "instant",
    [
        "2026-11-02T14:30:00+00:00",  # Exact 09:30 ET open.
        "2026-11-02T14:35:00+00:00",  # Former five-minute cutoff.
        "2026-11-02T15:15:00+00:00",  # 10:15 ET.
        "2026-11-02T17:00:00+00:00",  # Noon ET.
        "2026-11-02T19:30:00+00:00",  # 14:30 ET.
        "2026-11-02T20:59:59+00:00",  # Last second before regular close.
    ],
)
def test_execution_admits_entire_target_regular_session(
    ready_execution, monkeypatch, instant
):
    plan, transport, store = ready_execution
    now = datetime.fromisoformat(instant)
    monkeypatch.setattr(execution, "datetime", SimpleNamespace(now=lambda tz: now))
    result = execution.execute()
    assert result["status"] == "PASS"
    assert result["receipt"]["state"] == "FILLED"
    assert result["place_call_count"] == transport.placed == 1
    assert result["cancel_call_count"] == transport.canceled == 0
    assert result["attempt_consumed"] is True
    assert result["effect_disposition"] == "RECONCILED"
    assert load_binding(store.ownership_path, plan).plan_sha256 == plan.plan_sha256
    _assert_consumed_retry(transport, store)


@pytest.mark.parametrize(
    "instant,reason",
    [
        ("2026-10-30T16:00:00+00:00", "REGULAR_SESSION_NOT_OPEN"),
        ("2026-11-01T17:00:00+00:00", "REGULAR_SESSION_NOT_OPEN"),
        ("2026-11-02T12:00:00+00:00", "REGULAR_SESSION_NOT_OPEN"),
        ("2026-11-02T14:29:59+00:00", "REGULAR_SESSION_NOT_OPEN"),
        ("2026-11-02T21:00:00+00:00", "TARGET_SESSION_EXPIRED"),
        ("2026-11-02T23:00:00+00:00", "TARGET_SESSION_EXPIRED"),
        ("2026-11-03T17:00:00+00:00", "TARGET_SESSION_EXPIRED"),
    ],
)
def test_session_timing_block_has_no_provider_calls_or_consumption(
    ready_execution, monkeypatch, instant, reason
):
    plan, transport, store = ready_execution
    now = datetime.fromisoformat(instant)
    monkeypatch.setattr(execution, "datetime", SimpleNamespace(now=lambda tz: now))

    def forbidden(*args, **kwargs):
        raise AssertionError("timing must block before broker reads/review or marker")

    monkeypatch.setattr(transport, "get_accounts", forbidden)
    monkeypatch.setattr(transport, "review_equity_order", forbidden)
    monkeypatch.setattr(store, "start_attempt", forbidden)
    result = execution.execute()
    assert result["status"] == "BLOCKED"
    assert result["reason"] == reason
    assert result["place_call_count"] == transport.placed == 0
    assert result["cancel_call_count"] == transport.canceled == 0
    assert result["attempt_consumed"] is False
    assert result["effect_disposition"] == "NO_MUTATION"
    assert not store.marker.exists()
    assert not store.lifecycle.exists()
    assert not store.ownership_path.exists()
    assert plan.target_session == "2026-11-02"


def test_same_premarket_plan_can_execute_later_without_consumed_authority(
    ready_execution, monkeypatch
):
    plan, transport, store = ready_execution
    digest = plan.plan_sha256
    premarket = datetime(2026, 11, 2, 12, tzinfo=UTC)
    monkeypatch.setattr(
        execution, "datetime", SimpleNamespace(now=lambda tz: premarket)
    )
    blocked = execution.execute()
    assert blocked["reason"] == "REGULAR_SESSION_NOT_OPEN"
    assert blocked["place_call_count"] == transport.placed == 0
    assert blocked["cancel_call_count"] == transport.canceled == 0
    assert blocked["attempt_consumed"] is False
    assert blocked["effect_disposition"] == "NO_MUTATION"
    assert not store.marker.exists()
    assert not store.lifecycle.exists()
    assert not store.ownership_path.exists()

    noon = datetime(2026, 11, 2, 17, tzinfo=UTC)
    monkeypatch.setattr(execution, "datetime", SimpleNamespace(now=lambda tz: noon))
    result = execution.execute()
    assert result["status"] == "PASS"
    assert result["receipt"]["state"] == "FILLED"
    assert result["place_call_count"] == transport.placed == 1
    assert result["cancel_call_count"] == transport.canceled == 0
    assert result["attempt_consumed"] is True
    assert result["effect_disposition"] == "RECONCILED"
    assert load_binding(store.ownership_path, plan).plan_sha256 == digest
    assert plan.plan_sha256 == digest
    _assert_consumed_retry(transport, store)


def test_separate_requests_and_durable_consumption_precede_exact_nested_binding(
    ready_execution, monkeypatch
):
    plan, transport, store = ready_execution
    place = transport.place_equity_order

    def checked_place(arguments):
        assert store.marker.is_file()
        assert (
            json.loads(store.lifecycle.read_text().splitlines()[-1])["status"]
            == "LIVE_MUTATION_ATTEMPT_STARTED"
        )
        return place(arguments)

    monkeypatch.setattr(transport, "place_equity_order", checked_place)
    result = execution.execute()
    review = review_order_arguments(plan.requested_dollars, "SYNTHETIC")
    assert transport.review_arguments == [review]
    assert transport.placement_arguments == [
        {**review, "ref_id": execution.provider_ref_id(plan)}
    ]
    assert set(review) == {
        "account_number",
        "symbol",
        "side",
        "type",
        "dollar_amount",
        "market_hours",
        "time_in_force",
    }
    assert result["status"] == "PASS"
    assert result["receipt"]["provider_order_id"] == "provider-order-1"
    binding = load_binding(store.ownership_path, plan)
    assert binding.provider_order_id == "provider-order-1"
    assert binding.provider_order_id != execution.provider_ref_id(plan)


def test_provider_uuid_is_deterministic_and_separate_from_unchanged_local_sha():
    plan = _plan()
    ref = execution.provider_ref_id(plan)
    assert str(UUID(ref)) == ref
    assert UUID(ref).version == 5
    assert ref == str(uuid5(execution.P6_PROVIDER_REF_NAMESPACE, plan.plan_sha256))
    assert ref == execution.provider_ref_id(
        execution.plan_from_sanitized(plan.sanitized())
    )
    material = {
        name: getattr(plan, name)
        for name in plan.__dataclass_fields__
        if name != "plan_sha256"
    }
    other = LiveExecutionPlan.create(**(material | {"target_session": "2026-11-03"}))
    assert execution.provider_ref_id(other) != ref
    local = local_order_id(plan)
    assert (
        local
        == hashlib.sha256(
            ("p6-local-order/v1:" + plan.plan_sha256).encode("ascii")
        ).hexdigest()
    )
    assert len(local) == 64
    assert set(local) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {"data": None},
        {"data": []},
        {"data": {}},
        {"data": {"order": None}},
        {"data": {"order": []}},
        {"data": {"order": {}}},
        *[
            {"data": {"order": {"id": value}}}
            for value in (None, "", 42, "bad id", "x" * 129)
        ],
        {"data": {"id": "provider-order-1"}},
        {"data": {"order_id": "provider-order-1"}},
        {"data": {"order": {"ref_id": "provider-order-1"}}},
        {"data": {"ref_id": "provider-order-1"}},
    ],
)
def test_unusable_nested_provider_id_preserves_consumption_and_no_retry(
    ready_execution, monkeypatch, response
):
    _, transport, store = ready_execution

    def place(arguments):
        transport.placed += 1
        return response

    monkeypatch.setattr(transport, "place_equity_order", place)
    result = execution.execute()
    assert result["reason"] == result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["place_call_count"] == transport.placed == 1
    assert result["attempt_consumed"]
    assert result["receipt"] is None
    assert not store.ownership_path.exists()
    _assert_consumed_retry(transport, store)


@pytest.mark.parametrize(
    "changes",
    [
        {"order_checks": {"raw": "SECRET_PROVIDER_ALERT"}},
        {
            "customer_approval_required": True,
            "customer_approval_required_reason": "SECRET_PROVIDER_ALERT",
        },
        {"dollar_amount": "0.51"},
        {"symbol": "QQQ"},
        {"side": "sell"},
        {"type": "limit"},
    ],
)
def test_execution_review_drift_or_conditions_never_consume_or_place(
    ready_execution, monkeypatch, changes
):
    _, transport, store = ready_execution
    review = transport.review_equity_order

    def changed(arguments):
        payload = review(arguments)
        payload["data"].update(changes)
        return payload

    monkeypatch.setattr(transport, "review_equity_order", changed)
    result = execution.execute()
    assert result["status"] == "BLOCKED"
    assert result["effect_disposition"] == "NO_MUTATION"
    assert not result["attempt_consumed"]
    assert result["place_call_count"] == transport.placed == 0
    assert not store.marker.exists()
    assert "SECRET_PROVIDER_ALERT" not in json.dumps(result)
