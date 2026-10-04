"""PREPARE qualification tests use real adapters around inert transport/fakes."""

import ast
import hashlib
import json
import sqlite3
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

import trading_bot.review_paper.prepare_qualification as module
import trading_bot.review_paper.supervised_forward_paper as supervised
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper.forward_preview import build_review_paper_forward_preview
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
)
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionSchedule,
    admit_review_paper_session,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparation,
)
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparationStatus as Status,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter

AT = datetime(2026, 10, 2, 16, tzinfo=UTC)
BUFFER = timedelta(minutes=5)
AGE = timedelta(seconds=60, microseconds=1)


@pytest.fixture
def h(tmp_path, monkeypatch):
    transport = Mock(spec=["get_equity_quotes"])
    transport.get_equity_quotes.side_effect = AssertionError(
        "provider access outside bounded fake"
    )
    inputs = dict(
        store=ReviewPaperStore(
            tmp_path / "paper.sqlite", starting_cash=Decimal("10000")
        ),
        proposal=TradeProposal(
            UUID(int=1),
            Symbol("SPY"),
            OrderSide.BUY,
            Decimal("1.000"),
            AT,
            "private reason",
        ),
        schedule=ReviewPaperSessionSchedule(
            AT.date(), AT.replace(hour=13, minute=30), AT.replace(hour=20)
        ),
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
        adapter=RobinhoodReviewReadAdapter(transport),
        max_quote_age=AGE,
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        expected_source_head="a" * 40,
        expected_source_tree="b" * 40,
        evidence_path=tmp_path / "evidence.json",
    )
    state = SimpleNamespace(
        inputs=inputs, transport=transport, status=Status.READY_TO_PROCEED, result=None
    )

    def prepare(**kwargs):
        assert kwargs == {
            key: value
            for key, value in state.inputs.items()
            if key
            not in {"expected_source_head", "expected_source_tree", "evidence_path"}
        }
        state.result = _preparation(state)
        return state.result

    state.prepare = Mock(side_effect=prepare)
    monkeypatch.setattr(module, "prepare_review_paper_supervised_cycle", state.prepare)
    return state


def _preparation(h):
    values = {
        key: value
        for key, value in h.inputs.items()
        if key
        in {
            "store",
            "proposal",
            "schedule",
            "opening_buffer",
            "closing_buffer",
            "max_quote_age",
            "risk_limits",
            "new_trading_enabled",
        }
    }
    schedule = values["schedule"]
    initial_at = schedule.opens_at if h.status == Status.SESSION_NOT_ADMITTED else AT
    initial = admit_review_paper_session(
        schedule=schedule,
        as_of=initial_at,
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
    )
    values.update(status=h.status, initial_admission=initial)
    if h.status == Status.SESSION_NOT_ADMITTED:
        return ReviewPaperSupervisedPreparation(**values)
    observed = (
        schedule.closes_at
        if h.status == Status.SESSION_EXPIRED_DURING_ACQUISITION
        else AT
    )
    snapshot = ReviewPaperRiskPriceSnapshot(
        observed,
        (
            ReviewPaperRiskPriceMark(
                Symbol("SPY"),
                Decimal("100.123400"),
                observed - timedelta(microseconds=1),
            ),
        ),
    )
    quote = admit_review_paper_session(
        schedule=schedule, as_of=observed, opening_buffer=BUFFER, closing_buffer=BUFFER
    )
    values.update(price_snapshot=snapshot, quote_admission=quote)
    if h.status == Status.SESSION_EXPIRED_DURING_ACQUISITION:
        return ReviewPaperSupervisedPreparation(**values)
    preview = build_review_paper_forward_preview(
        store=values["store"],
        proposal=values["proposal"],
        price_snapshot=snapshot,
        risk_limits=values["risk_limits"],
        new_trading_enabled=values["new_trading_enabled"],
    )
    values.update(
        preview=preview,
        durable_history=(),
        quote_valid_until=snapshot.marks[0].source_at + AGE,
    )
    return ReviewPaperSupervisedPreparation(**values)


@pytest.mark.parametrize(
    "key",
    [
        "store",
        "proposal",
        "schedule",
        "opening_buffer",
        "closing_buffer",
        "adapter",
        "max_quote_age",
        "risk_limits",
        "new_trading_enabled",
        "evidence_path",
    ],
)
def test_bad_exact_types_before_access(h, monkeypatch, key):
    fingerprint = Mock(side_effect=AssertionError("durable access before admission"))
    monkeypatch.setattr(module, "_read_durable_snapshot", fingerprint)
    with pytest.raises(TypeError):
        module.run_review_paper_prepare_qualification(**{**h.inputs, key: object()})
    h.prepare.assert_not_called()
    fingerprint.assert_not_called()
    h.transport.get_equity_quotes.assert_not_called()


@pytest.mark.parametrize(
    "key,value",
    [
        ("expected_source_head", "A" * 40),
        ("expected_source_tree", "g" * 40),
        ("expected_source_head", "a" * 39),
        ("expected_source_tree", 1),
        ("max_quote_age", timedelta(0)),
        ("max_quote_age", timedelta(seconds=-1)),
        ("opening_buffer", timedelta(seconds=-1)),
        ("closing_buffer", timedelta(days=1)),
        ("opening_buffer", timedelta(hours=6, minutes=30)),
        ("closing_buffer", timedelta(minutes=30)),
        ("evidence_path", Path("relative.json")),
    ],
)
def test_invalid_values_before_prepare(h, key, value):
    if key == "closing_buffer" and value == timedelta(minutes=30):
        h.inputs["opening_buffer"] = timedelta(hours=6)
    with pytest.raises((ValueError, TypeError)):
        module.run_review_paper_prepare_qualification(**{**h.inputs, key: value})
    h.prepare.assert_not_called()
    h.transport.get_equity_quotes.assert_not_called()


def test_existing_and_store_evidence_rejected(h):
    path = h.inputs["evidence_path"]
    path.write_text("preserve")
    with pytest.raises(FileExistsError):
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert path.read_text() == "preserve"
    with pytest.raises(ValueError, match="differ"):
        module.run_review_paper_prepare_qualification(
            **{**h.inputs, "evidence_path": h.inputs["store"].path}
        )
    h.prepare.assert_not_called()


def test_missing_and_unreadable_store_before_prepare(h, monkeypatch):
    h.inputs["store"]._path = h.inputs["store"].path.parent / "missing.sqlite"
    with pytest.raises(ValueError, match="existing"):
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert not h.inputs["store"].path.exists()
    h.inputs["store"].path.write_text("not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        module.run_review_paper_prepare_qualification(**h.inputs)
    h.prepare.assert_not_called()


@pytest.mark.parametrize("status", list(Status))
def test_status_serialization_exact_return_and_once(h, status):
    h.status = status
    if status == Status.RISK_REJECTED:
        h.inputs["new_trading_enabled"] = False
    result = module.run_review_paper_prepare_qualification(**h.inputs)
    assert result is h.result
    h.prepare.assert_called_once()
    evidence = json.loads(h.inputs["evidence_path"].read_text())
    assert evidence["schema"] == "arch131-q-prepare-qualification/v1"
    assert evidence["source_head"] == "a" * 40 and evidence["source_tree"] == "b" * 40
    assert (
        evidence["execute_invoked"] is False
        and evidence["pipeline_result_present"] is False
    )
    assert evidence["durable_before"] == evidence["durable_after"]
    assert evidence["proposal"] == {
        "proposal_id": str(UUID(int=1)),
        "symbol": "SPY",
        "side": "BUY",
        "desired_quantity": "1.000",
        "created_at": AT.isoformat(),
    }
    assert evidence["schedule"] == {
        "session_date": AT.date().isoformat(),
        "opens_at": h.inputs["schedule"].opens_at.isoformat(),
        "closes_at": h.inputs["schedule"].closes_at.isoformat(),
    }
    section = evidence["preparation"]
    assert section["status"] == status.value
    assert section["initial_admission"] == module._admission(result.initial_admission)
    if result.price_snapshot is None:
        assert all(
            section[name] is None
            for name in (
                "price_snapshot",
                "quote_admission",
                "risk_preview",
                "quote_valid_until",
            )
        )
    else:
        mark = section["price_snapshot"]["marks"][0]
        assert mark == {
            "symbol": "SPY",
            "price": "100.123400",
            "source_at": result.price_snapshot.marks[0].source_at.isoformat(),
        }
        assert section["quote_admission"] == module._admission(result.quote_admission)
    if result.preview is None:
        assert section["risk_preview"] is None and section["quote_valid_until"] is None
    else:
        preview = section["risk_preview"]
        assert preview == {
            "requested_quantity": "1.000",
            "risk_outcome": result.preview.risk_decision.outcome.value,
            "approved_quantity": str(result.preview.risk_decision.approved_quantity),
            "reason_codes": [
                reason.code.value for reason in result.preview.risk_decision.reasons
            ],
            "cash": "10000",
            "equity": "10000",
            "current_price": "100.123400",
            "total_market_exposure": "0",
            "current_position_quantity": "0",
            "current_position_market_value": "0.000000",
            "projected_position_quantity": str(
                result.preview.projected_position_quantity
            ),
            "projected_position_market_value": str(
                result.preview.projected_position_market_value
            ),
            "projected_total_market_exposure": str(
                result.preview.projected_total_market_exposure
            ),
        }
        assert section["quote_valid_until"] == result.quote_valid_until.isoformat()
    assert "private reason" not in h.inputs["evidence_path"].read_text()
    from trading_bot.robinhood_prepare_qualification_verifier import (
        verify_robinhood_prepare_qualification,
    )

    verified = verify_robinhood_prepare_qualification(
        store_path=h.inputs["store"].path,
        evidence_path=h.inputs["evidence_path"],
        expected_source_head=h.inputs["expected_source_head"],
        expected_source_tree=h.inputs["expected_source_tree"],
        expected_proposal_id=h.inputs["proposal"].proposal_id,
    )
    assert verified.preparation_status == status.value


def test_fingerprint_read_only_twice_and_write_once_after_prepare(h, monkeypatch):
    connect = sqlite3.connect
    events = []

    def readonly(database, **kwargs):
        assert (
            database.startswith("file:")
            and database.endswith("?mode=ro")
            and kwargs == {"uri": True}
        )
        connection = connect(database, **kwargs)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("UPDATE metadata SET value='tamper'")
        connection.rollback()
        events.append("snapshot")
        return connection

    # Isolate harness connections with an already built preparation.
    result = _preparation(h)

    def prepare(**kwargs):
        events.append("prepare")
        return result

    h.prepare.side_effect = prepare
    monkeypatch.setattr(module.sqlite3, "connect", readonly)
    original_open = Path.open

    def evidence_open(path, mode="r", *args, **kwargs):
        if path == h.inputs["evidence_path"]:
            assert mode == "x"
            events.append("write")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", evidence_open)
    assert module.run_review_paper_prepare_qualification(**h.inputs) is result
    assert events == ["snapshot", "prepare", "snapshot", "write"]


def test_fingerprint_complete_columns_rows_metadata_and_order(h):
    path = h.inputs["store"].path
    with sqlite3.connect(path) as connection:
        columns = [
            row[1] for row in connection.execute("PRAGMA table_info(review_fills)")
        ]
        placeholders = ",".join("?" for _ in columns)
        for identity in ("b", "a"):
            connection.execute(
                f"INSERT INTO review_fills VALUES ({placeholders})",
                [identity + str(index) for index in range(len(columns))],
            )
        metadata = connection.execute(
            "SELECT key, value FROM metadata ORDER BY key"
        ).fetchall()
        cursor = connection.execute(
            "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
        )
        rows = cursor.fetchall()
        names = [entry[0] for entry in cursor.description]
    expected = hashlib.sha256(
        json.dumps(
            {"metadata": metadata, "columns": names, "rows": rows, "record_count": 2},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    before = module._read_durable_snapshot(path)
    assert before.sha256 == expected and before.record_count == 2
    assert before == module._read_durable_snapshot(path)
    assert asdict(before)["metadata"] == tuple(metadata)
    with pytest.raises(FrozenInstanceError):
        before.sha256 = "changed"
    for column in columns:
        with sqlite3.connect(path) as connection:
            connection.execute(
                f'UPDATE review_fills SET "{column}" = "{column}" || ?', ("x",)
            )
        after = module._read_durable_snapshot(path)
        assert after.sha256 != before.sha256, column
        before = after
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE review_fills ADD COLUMN extra TEXT")
    assert module._read_durable_snapshot(path).sha256 != before.sha256


@pytest.mark.parametrize("drift", ["metadata", "record_count", "sha256"])
def test_each_descriptor_field_must_match(h, monkeypatch, drift):
    before = module._read_durable_snapshot(h.inputs["store"].path)
    changes = {
        "metadata": (("tamper", "value"),),
        "record_count": 1,
        "sha256": "c" * 64,
    }
    monkeypatch.setattr(
        module,
        "_read_durable_snapshot",
        Mock(side_effect=[before, replace(before, **{drift: changes[drift]})]),
    )
    with pytest.raises(RuntimeError, match="durable state changed"):
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert not h.inputs["evidence_path"].exists()
    h.prepare.assert_called_once()


def test_actual_isolated_durable_mutation_fails_without_evidence(h):
    result = _preparation(h)

    def mutate(**kwargs):
        with sqlite3.connect(h.inputs["store"].path) as connection:
            connection.execute(
                "UPDATE metadata SET value='9999' WHERE key='starting_cash'"
            )
        return result

    h.prepare.side_effect = mutate
    with pytest.raises(RuntimeError, match="durable state changed"):
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert not h.inputs["evidence_path"].exists()
    h.prepare.assert_called_once()


def test_prepare_exception_identity_no_retry(h):
    error = RuntimeError("fake PREPARE failure")
    h.prepare.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert caught.value is error
    h.prepare.assert_called_once()
    assert not h.inputs["evidence_path"].exists()


def test_real_prepare_provider_exception_identity_no_retry(h, monkeypatch):
    error = RuntimeError("fake provider failure")
    h.transport.get_equity_quotes.side_effect = error
    monkeypatch.setattr(
        supervised, "datetime", SimpleNamespace(now=Mock(return_value=AT))
    )
    monkeypatch.setattr(
        module,
        "prepare_review_paper_supervised_cycle",
        supervised.prepare_review_paper_supervised_cycle,
    )
    with pytest.raises(RuntimeError) as caught:
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert caught.value is error
    h.transport.get_equity_quotes.assert_called_once()
    assert not h.inputs["evidence_path"].exists()


def test_racing_evidence_create_never_overwrites(h):
    result = _preparation(h)

    def race(**kwargs):
        h.inputs["evidence_path"].write_text("preserve racing artifact")
        return result

    h.prepare.side_effect = race
    with pytest.raises(FileExistsError):
        module.run_review_paper_prepare_qualification(**h.inputs)
    assert h.inputs["evidence_path"].read_text() == "preserve racing artifact"
    h.prepare.assert_called_once()


def test_canonical_multiple_marks_and_sanitized_only(h):
    snapshot = ReviewPaperRiskPriceSnapshot(
        AT,
        tuple(
            ReviewPaperRiskPriceMark(Symbol(name), Decimal("1.20"), AT)
            for name in ("AAPL", "SPY")
        ),
    )
    result = SimpleNamespace(
        status=Status.SESSION_EXPIRED_DURING_ACQUISITION,
        initial_admission=_preparation(h).initial_admission,
        price_snapshot=snapshot,
        quote_admission=None,
        preview=None,
        quote_valid_until=None,
    )
    marks = module._preparation_evidence(result)["price_snapshot"]["marks"]
    assert [mark["symbol"] for mark in marks] == ["AAPL", "SPY"]
    assert all(set(mark) == {"symbol", "price", "source_at"} for mark in marks)


def test_source_has_no_execution_pipeline_authority():
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "execute_review_paper_supervised_cycle",
        "run_robinhood_forward_paper_cycle",
        "ExecutionInstruction",
        "uuid4",
        "uuid5",
        "RiskManager",
        "record_market_review",
        "sleep",
    }
    assert not forbidden.intersection(
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    )
    assert not forbidden.intersection(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ReviewPaperStore"
        for node in ast.walk(tree)
    )
    imported = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        value
        and any(
            part in value
            for part in (
                "execution",
                "transport",
                "oauth",
                "paper_pipeline",
                "paper_operator",
                "intent_bridge",
            )
        )
        for value in imported
    )
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert (
        sum(
            isinstance(node.func, ast.Name)
            and node.func.id == "prepare_review_paper_supervised_cycle"
            for node in calls
        )
        == 1
    )
    assert (
        sum(
            isinstance(node.func, ast.Name) and node.func.id == "_read_durable_snapshot"
            for node in calls
        )
        == 2
    )
    assert not any(
        isinstance(node, (ast.While, ast.AsyncFunctionDef)) for node in ast.walk(tree)
    )


def test_real_prepare_fake_transport_ready_has_no_durable_effect(h, monkeypatch):
    import trading_bot.review_paper.risk_price_acquisition as acquisition

    quote = {
        "symbol": "SPY",
        "adjusted_previous_close": "100",
        "ask_price": "101",
        "bid_price": "99",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "100.123400",
        "previous_close": "100",
        "previous_close_date": None,
        "state": "active",
        "venue_ask_time": AT.isoformat(),
        "venue_bid_time": AT.isoformat(),
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": AT.isoformat(),
    }
    h.transport.get_equity_quotes.side_effect = None
    h.transport.get_equity_quotes.return_value = {
        "data": {"results": [{"quote": quote, "close": None}]}
    }
    monkeypatch.setattr(
        supervised, "datetime", SimpleNamespace(now=Mock(return_value=AT))
    )
    monkeypatch.setattr(
        acquisition, "datetime", SimpleNamespace(now=Mock(return_value=AT))
    )
    monkeypatch.setattr(
        module,
        "prepare_review_paper_supervised_cycle",
        supervised.prepare_review_paper_supervised_cycle,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("execution authority invoked")

    monkeypatch.setattr(supervised, "execute_review_paper_supervised_cycle", forbidden)
    monkeypatch.setattr(supervised, "run_robinhood_forward_paper_cycle", forbidden)
    monkeypatch.setattr(ReviewPaperStore, "record_market_review", forbidden)
    before = h.inputs["store"].path.read_bytes()
    result = module.run_review_paper_prepare_qualification(**h.inputs)
    assert result.status is Status.READY_TO_PROCEED
    h.transport.get_equity_quotes.assert_called_once_with({"symbols": ["SPY"]})
    assert before == h.inputs["store"].path.read_bytes()
    assert h.inputs["store"].history() == ()
