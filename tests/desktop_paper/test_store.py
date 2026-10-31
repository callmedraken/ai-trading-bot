from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, Inexact, localcontext
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from trading_bot.desktop_paper.configuration import create_paper_evaluation_config
from trading_bot.desktop_paper.models import PaperCycleInput, PaperCycleKind
from trading_bot.desktop_paper.store import (
    PaperEvaluationStore,
    PaperEvaluationStoreConflictError,
    PaperEvaluationStoreCorruptionError,
)
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.risk import RiskOutcome, RiskReasonCode

ACCOUNT_ID = UUID("addfb265-cc4e-5af3-a4a9-85ca87610ebf")
START = datetime(2026, 10, 1, 13, 30, tzinfo=UTC)


def _cycle(
    index: int, *, side: OrderSide = OrderSide.BUY, quantity: str = "1"
) -> PaperCycleInput:
    at = START + timedelta(days=index)
    session = at.date().isoformat()
    proposal = TradeProposal(
        proposal_id=uuid5(NAMESPACE_URL, f"proposal:{session}"),
        symbol=Symbol("QQQ"),
        side=side,
        desired_quantity=Decimal(quantity),
        created_at=at,
        reason="synthetic paper test proposal",
    )
    return PaperCycleInput(
        execution_session_id=session,
        execution_index=index,
        symbol=Symbol("QQQ"),
        observation_id=uuid5(NAMESPACE_URL, f"observation:{session}"),
        completed_history_cutoff=(at - timedelta(days=1)).date().isoformat(),
        observation_open=Decimal("100"),
        executed_at=at,
        proposal=proposal,
    )


def _open(tmp_path, paper_config, *, hook=None) -> PaperEvaluationStore:
    return PaperEvaluationStore(
        tmp_path / "paper.sqlite",
        account_id=ACCOUNT_ID,
        config=paper_config,
        fault_hook=hook,
    )


def test_commit_reopens_exact_account_fill_chain_and_slot_readback(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    cycle = _cycle(1)
    first = store.commit_cycle(cycle)
    exact = store.commit_cycle(
        replace(
            cycle,
            proposal=replace(
                cycle.proposal, proposal_id=uuid5(NAMESPACE_URL, "irrelevant-retry-id")
            ),
        )
    )

    assert exact == first
    assert first.kind is PaperCycleKind.FILLED
    assert first.fill is not None
    assert first.fill.price == Decimal("100.05")
    assert first.fill.commission == Decimal("1")
    assert first.account.cash == Decimal("99898.95")
    assert first.account.positions[Symbol("QQQ")].quantity == Decimal("1")
    assert first.account.marked_equity == Decimal("99998.95")
    assert len(first.account.fills) == 1

    reopened = _open(tmp_path, paper_config)
    state = reopened.load_state()
    assert state.cursor_index == 1
    assert state.execution_session_id == cycle.execution_session_id
    assert state.latest_result == first
    assert state.account == first.account
    assert reopened.latest_cycle() == first
    scaled = replace(
        cycle,
        observation_open=Decimal("100.00"),
        proposal=replace(cycle.proposal, desired_quantity=Decimal("1.000")),
    )
    assert reopened.commit_cycle(scaled) == first
    scaled_config = create_paper_evaluation_config(
        paper_config.binding,
        replace(paper_config.policy, starting_cash=Decimal("100000.00")),
    )
    assert _open(tmp_path, scaled_config).load_state() == state


def test_before_commit_fault_rolls_back_cycle_cursor_and_fill(
    tmp_path, paper_config
) -> None:
    def fail(stage: str) -> None:
        if stage == "before_commit":
            raise RuntimeError("injected-before-commit")

    store = _open(tmp_path, paper_config, hook=fail)
    with pytest.raises(RuntimeError, match="injected-before-commit"):
        store.commit_cycle(_cycle(1))

    reopened = _open(tmp_path, paper_config)
    state = reopened.load_state()
    assert state.cursor_index == 0
    assert state.latest_result is None
    assert state.account.fills == ()


def test_after_commit_before_ack_fault_reads_exact_result_without_duplicate_fill(
    tmp_path, paper_config
) -> None:
    def fail(stage: str) -> None:
        if stage == "after_commit":
            raise RuntimeError("injected-after-commit")

    store = _open(tmp_path, paper_config, hook=fail)
    cycle = _cycle(1)
    with pytest.raises(RuntimeError, match="injected-after-commit"):
        store.commit_cycle(cycle)

    reopened = _open(tmp_path, paper_config)
    result = reopened.latest_cycle()
    assert result is not None
    assert result.kind is PaperCycleKind.FILLED
    assert result.fill is not None
    assert reopened.load_state().account.fills == (result.fill,)
    assert reopened.commit_cycle(cycle) == result
    assert len(reopened.load_state().account.fills) == 1


def test_conflicting_slot_material_is_diagnosed_without_second_effect(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    original = _cycle(1)
    committed = store.commit_cycle(original)
    conflict = _cycle(1, quantity="2")

    with pytest.raises(
        PaperEvaluationStoreConflictError, match="SLOT_MATERIAL_CONFLICT"
    ):
        store.commit_cycle(conflict)

    reopened = _open(tmp_path, paper_config)
    assert reopened.latest_cycle() == committed
    assert len(reopened.load_state().account.fills) == 1
    with sqlite3.connect(tmp_path / "paper.sqlite") as connection:
        assert connection.execute(
            "SELECT count(*) FROM chain_events WHERE event_type='CONFLICT'"
        ).fetchone() == (1,)


@pytest.mark.parametrize("identity_role", ["order", "fill", "fill-event"])
def test_duplicate_order_fill_or_event_identity_is_rejected_and_diagnosed(
    tmp_path, paper_config, monkeypatch, identity_role
) -> None:
    import trading_bot.desktop_paper.engine as engine_module

    original = engine_module.financial_identity
    fixed = UUID("c6138608-73f3-50ba-a8ae-af1dc836aa2c")

    def collision(name: str, material: str) -> UUID:
        if name == identity_role:
            return fixed
        return original(name, material)

    monkeypatch.setattr(engine_module, "financial_identity", collision)
    store = _open(tmp_path, paper_config)
    store.commit_cycle(_cycle(1))
    with pytest.raises(
        PaperEvaluationStoreConflictError, match="DUPLICATE_FINANCIAL_IDENTITY"
    ):
        store.commit_cycle(_cycle(2))

    assert store.load_state().cursor_index == 1
    assert len(store.load_state().account.fills) == 1
    with sqlite3.connect(tmp_path / "paper.sqlite") as connection:
        assert connection.execute(
            "SELECT count(*) FROM chain_events WHERE event_type='CONFLICT'"
        ).fetchone() == (1,)


def test_kill_pauses_without_consuming_slot_and_stopped_clear_is_bounded(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    control = store.latch_kill()
    assert control.kill_latched is True
    with pytest.raises(PaperEvaluationStoreConflictError, match="ACTIVE"):
        store.clear_kill_when_stopped(active_worker=True)

    paused = store.commit_cycle(_cycle(1))
    assert paused.kind is PaperCycleKind.KILL_LATCHED
    assert paused.cursor_index == 0
    assert store.load_state().latest_result is None

    store.clear_kill_when_stopped(active_worker=False)
    committed = store.commit_cycle(_cycle(1))
    assert committed.kind is PaperCycleKind.FILLED
    assert committed.control.kill_latched is False


def test_new_buys_use_risk_manager_but_sell_remains_available(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    bought = store.commit_cycle(_cycle(1, quantity="2"))
    assert bought.kind is PaperCycleKind.FILLED
    store.set_new_buys_enabled(False)

    rejected = store.commit_cycle(_cycle(2, quantity="1"))
    assert rejected.kind is PaperCycleKind.RISK_REJECTED
    assert rejected.risk_decision is not None
    assert rejected.risk_decision.outcome is RiskOutcome.REJECTED
    assert rejected.risk_decision.reasons[0].code is RiskReasonCode.TRADING_DISABLED

    sold = store.commit_cycle(_cycle(3, side=OrderSide.SELL, quantity="1"))
    assert sold.kind is PaperCycleKind.FILLED
    assert sold.fill is not None and sold.fill.side is OrderSide.SELL
    assert sold.account.positions[Symbol("QQQ")].quantity == Decimal("1")


def test_whole_share_and_position_and_notional_limits_use_synthetic_fill_price(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    result = store.commit_cycle(_cycle(1, quantity="1000"))

    assert result.kind is PaperCycleKind.FILLED
    assert result.risk_context is not None
    assert result.risk_decision is not None
    assert result.risk_context.current_price == Decimal("100.05")
    assert (
        result.fill is not None
        and result.fill.price == result.risk_context.current_price
    )
    assert result.risk_decision.approved_quantity == Decimal("199")
    assert result.fill.quantity == Decimal("199")
    assert result.fill.gross_amount <= Decimal("20000")
    assert result.account.positions[Symbol("QQQ")].quantity == Decimal("199")


def test_low_ambient_decimal_precision_and_traps_do_not_change_cycle_result(
    tmp_path, paper_config
) -> None:
    first_store = PaperEvaluationStore(
        tmp_path / "first.sqlite", account_id=ACCOUNT_ID, config=paper_config
    )
    baseline = first_store.commit_cycle(_cycle(1, quantity="10"))
    second_store = PaperEvaluationStore(
        tmp_path / "second.sqlite", account_id=ACCOUNT_ID, config=paper_config
    )
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.rounding = ROUND_DOWN
        ambient.traps[Inexact] = True
        changed = second_store.commit_cycle(_cycle(1, quantity="10"))

    assert changed == baseline


def test_config_revision_change_is_rejected_without_new_effect(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    result = store.commit_cycle(_cycle(1))
    changed_config = create_paper_evaluation_config(
        paper_config.binding,
        replace(paper_config.policy, replay_interval_seconds=Decimal("0.20")),
    )

    with pytest.raises(PaperEvaluationStoreCorruptionError, match="REVISION_MISMATCH"):
        PaperEvaluationStore(
            tmp_path / "paper.sqlite", account_id=ACCOUNT_ID, config=changed_config
        )

    reopened = _open(tmp_path, paper_config)
    assert reopened.latest_cycle() == result
    assert len(reopened.load_state().account.fills) == 1


@pytest.mark.parametrize(
    "corruption",
    ["hash", "cleared-chain", "orphan-slot", "effect-event-ref", "slot-event-ref"],
)
def test_corrupt_or_incomplete_durable_chain_fails_closed(
    tmp_path, paper_config, corruption
) -> None:
    store = _open(tmp_path, paper_config)
    store.commit_cycle(_cycle(1))
    database = tmp_path / "paper.sqlite"
    with sqlite3.connect(database) as connection:
        if corruption == "hash":
            connection.execute(
                "UPDATE chain_events SET payload='{}' WHERE event_type='CYCLE'"
            )
        elif corruption == "cleared-chain":
            connection.execute("DELETE FROM effect_identities")
            connection.execute("DELETE FROM cycle_slots")
            connection.execute("DELETE FROM chain_events")
        elif corruption == "orphan-slot":
            config_event = connection.execute(
                "SELECT event_id FROM chain_events WHERE event_type='CONFIGURATION'"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO cycle_slots"
                "(account_id,source_lane,symbol,session_id,cycle_id,event_id) "
                "VALUES(?,?,?,?,?,?)",
                (
                    str(ACCOUNT_ID),
                    "OPEN_REPLAY",
                    "QQQ",
                    "orphan-session",
                    "orphan-cycle",
                    config_event,
                ),
            )
        else:
            config_event = connection.execute(
                "SELECT event_id FROM chain_events WHERE event_type='CONFIGURATION'"
            ).fetchone()[0]
            table = (
                "effect_identities"
                if corruption == "effect-event-ref"
                else "cycle_slots"
            )
            connection.execute(f"UPDATE {table} SET event_id=?", (config_event,))

    with pytest.raises(PaperEvaluationStoreCorruptionError):
        _open(tmp_path, paper_config)


@pytest.mark.parametrize(
    "kind", ["preexisting-empty", "bad-version", "missing-unique", "missing-fk"]
)
def test_malformed_or_incompatible_schema_is_not_repaired(
    tmp_path, paper_config, kind
) -> None:
    database = tmp_path / "paper.sqlite"
    if kind == "preexisting-empty":
        sqlite3.connect(database).close()
    else:
        store = _open(tmp_path, paper_config)
        store.close()
        with sqlite3.connect(database) as connection:
            if kind == "bad-version":
                connection.execute("PRAGMA user_version=77")
            elif kind == "missing-unique":
                connection.execute(
                    "ALTER TABLE effect_identities RENAME TO old_effect_identities"
                )
                connection.execute(
                    "CREATE TABLE effect_identities("
                    "identity TEXT,kind TEXT NOT NULL,cycle_id TEXT NOT NULL,"
                    "event_id TEXT NOT NULL REFERENCES chain_events(event_id))"
                )
                connection.execute("DROP TABLE old_effect_identities")
            else:
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute("ALTER TABLE cycle_slots RENAME TO old_cycle_slots")
                connection.execute(
                    "CREATE TABLE cycle_slots("
                    "account_id TEXT NOT NULL,source_lane TEXT NOT NULL,"
                    "symbol TEXT NOT NULL,session_id TEXT NOT NULL,"
                    "cycle_id TEXT NOT NULL UNIQUE,event_id TEXT NOT NULL UNIQUE,"
                    "PRIMARY KEY(account_id,source_lane,symbol,session_id))"
                )
                connection.execute("DROP TABLE old_cycle_slots")

    with pytest.raises(PaperEvaluationStoreCorruptionError):
        _open(tmp_path, paper_config)


def test_stop_before_admission_rolls_back_and_active_transaction_may_commit(
    tmp_path, paper_config
) -> None:
    store = _open(tmp_path, paper_config)
    with pytest.raises(InterruptedError):
        store.commit_cycle(_cycle(1), stop_requested=lambda: True)
    assert store.load_state().cursor_index == 0

    stop = False

    def request_stop_after_admission(stage: str) -> None:
        nonlocal stop
        if stage == "admitted":
            stop = True

    admitted = PaperEvaluationStore(
        tmp_path / "paper.sqlite",
        account_id=ACCOUNT_ID,
        config=paper_config,
        fault_hook=request_stop_after_admission,
    )
    result = admitted.commit_cycle(_cycle(1), stop_requested=lambda: stop)
    assert result.kind is PaperCycleKind.FILLED
    assert admitted.load_state().cursor_index == 1


def test_kill_race_is_ordered_by_the_store_transaction(tmp_path, paper_config) -> None:
    admitted = threading.Event()
    release = threading.Event()
    results = []
    errors = []

    def hold_admitted_cycle(stage: str) -> None:
        if stage == "admitted":
            admitted.set()
            if not release.wait(5):
                raise TimeoutError("test did not release the admitted cycle")

    store = _open(tmp_path, paper_config, hook=hold_admitted_cycle)

    def run_cycle() -> None:
        try:
            results.append(store.commit_cycle(_cycle(1)))
        except Exception as error:  # noqa: BLE001 - thread result transport
            errors.append(error)

    def latch_kill() -> None:
        try:
            store.latch_kill()
        except Exception as error:  # noqa: BLE001 - thread result transport
            errors.append(error)

    cycle_thread = threading.Thread(target=run_cycle)
    cycle_thread.start()
    assert admitted.wait(5)
    kill_thread = threading.Thread(target=latch_kill)
    kill_thread.start()
    release.set()
    cycle_thread.join(5)
    kill_thread.join(5)

    assert not cycle_thread.is_alive()
    assert not kill_thread.is_alive()
    assert errors == []
    assert results[0].kind is PaperCycleKind.FILLED
    assert store.load_state().control.kill_latched is True
    paused = store.commit_cycle(_cycle(2))
    assert paused.kind is PaperCycleKind.KILL_LATCHED
    assert store.load_state().cursor_index == 1
