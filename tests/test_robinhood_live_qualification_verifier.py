from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.robinhood_live_qualification_verifier import (
    RobinhoodLiveQualificationVerificationError,
    main,
    verify_robinhood_131l_live_qualification,
)

HEAD = "a" * 40
TREE = "b" * 40
PRIOR_ORDER = UUID("22222222-131a-4000-8000-000000000001")
ORDER = UUID("22222222-131b-4000-8000-000000000001")
PRIOR_FILL = "769.870000"
NEW_FILL = "771.320000"
PRIOR_TIME = "2026-10-03T00:00:00.232470+00:00"
NEW_TIME = "2026-10-05T14:00:00+00:00"


def _operator() -> dict[str, object]:
    return {
        "source_head": HEAD,
        "source_tree": TREE,
        "status": "PASS",
        "phase": "complete",
        "symbol": "SPY",
        "side": "BUY",
        "quantity": "1.000",
        "order_type": "MARKET",
        "get_accounts_calls": 1,
        "get_equity_orders_calls": 2,
        "review_equity_order_calls": 1,
        "get_equity_quotes_calls": 0,
        "baseline_order_pages": 1,
        "post_review_order_pages": 1,
        "paper_record_count": 2,
        "replay": False,
        "review_echo_validated": True,
        "quote_fill_validated": True,
        "disclosure_present": True,
        "interactive_reauth_count": 0,
        "placement_calls": 0,
        "cancellation_calls": 0,
        "options_mutation_calls": 0,
        "crypto_mutation_calls": 0,
    }


def _summary(store: Path, evidence: Path) -> dict[str, object]:
    return {
        "schema": "arch131-l-live-qualification/v1",
        "branch": "feature/robinhood-review-paper-mode",
        "head": HEAD,
        "tree": TREE,
        "store": str(store),
        "order_id": str(ORDER),
        "proposal_id": "11111111-131b-4000-8000-000000000001",
        "qualification_mark": "769.650000",
        "before": {
            "record_count": 1,
            "cash": "99230.130000",
            "spy_quantity": "1",
        },
        "decision": {
            "desired_quantity": "2",
            "outcome": "RESIZED",
            "approved_quantity": "1.000",
            "reason_codes": [
                "MAX_POSITION_PERCENT",
                "QUANTITY_INCREMENT",
            ],
        },
        "operator": _operator(),
        "after": {
            "record_count": 2,
            "cash": "98458.810000",
            "spy_quantity": "2.000",
            "new_fill_price": NEW_FILL,
            "new_fill_time": NEW_TIME,
        },
        "operator_evidence_file": str(evidence),
    }


def _write_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (("schema_version", "2"), ("starting_cash", "100000")),
        )
        connection.execute(
            """
            CREATE TABLE review_fills (
                paper_trade_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL UNIQUE,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                desired_quantity TEXT NOT NULL,
                approved_quantity TEXT NOT NULL,
                risk_outcome TEXT NOT NULL,
                risk_reason_codes TEXT NOT NULL,
                fill_price TEXT NOT NULL,
                commission TEXT NOT NULL,
                filled_at TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO review_fills (
                paper_trade_id, order_id, symbol, side, desired_quantity,
                approved_quantity, risk_outcome, risk_reason_codes, fill_price,
                commission, filled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    "prior-trade",
                    str(PRIOR_ORDER),
                    "SPY",
                    "BUY",
                    "1",
                    "1",
                    "APPROVED",
                    "",
                    PRIOR_FILL,
                    "0",
                    PRIOR_TIME,
                ),
                (
                    "new-trade",
                    str(ORDER),
                    "SPY",
                    "BUY",
                    "2",
                    "1.000",
                    "RESIZED",
                    "MAX_POSITION_PERCENT|QUANTITY_INCREMENT",
                    NEW_FILL,
                    "0",
                    NEW_TIME,
                ),
            ),
        )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    store = (tmp_path / "paper.sqlite").resolve()
    evidence = (tmp_path / "operator-evidence.json").resolve()
    summary = (tmp_path / "qualification-summary.json").resolve()
    _write_store(store)
    evidence.write_text(json.dumps(_operator()), encoding="utf-8")
    summary.write_text(json.dumps(_summary(store, evidence)), encoding="utf-8")
    return store, evidence, summary


def _verify(store: Path, evidence: Path, summary: Path):
    return verify_robinhood_131l_live_qualification(
        store_path=store,
        operator_evidence_path=evidence,
        summary_path=summary,
        expected_source_head=HEAD,
        expected_source_tree=TREE,
        expected_prior_order_id=PRIOR_ORDER,
        expected_order_id=ORDER,
    )


def test_verifies_exact_frozen_131l_qualification(tmp_path):
    store, evidence, summary = _fixture(tmp_path)
    original = store.read_bytes()

    result = _verify(store, evidence, summary)

    assert result.source_head == HEAD
    assert result.source_tree == TREE
    assert result.record_count == 2
    assert result.cash == Decimal("98458.810000")
    assert str(result.symbol) == "SPY"
    assert str(result.position_quantity) == "2.000"
    assert result.order_id == ORDER
    assert str(result.fill_price) == NEW_FILL
    assert result.fill_time.isoformat() == NEW_TIME
    assert store.read_bytes() == original


def test_sqlite_is_opened_read_only(tmp_path, monkeypatch):
    store, evidence, summary = _fixture(tmp_path)
    real_connect = sqlite3.connect
    calls = []

    def observed(database, *args, **kwargs):
        calls.append((database, args, kwargs))
        return real_connect(database, *args, **kwargs)

    import trading_bot.robinhood_live_qualification_verifier as verifier

    monkeypatch.setattr(verifier.sqlite3, "connect", observed)
    _verify(store, evidence, summary)

    assert len(calls) == 1
    database, args, kwargs = calls[0]
    assert database == store.as_uri() + "?mode=ro"
    assert args == ()
    assert kwargs == {"uri": True}


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "FAIL"),
        ("phase", "review"),
        ("review_equity_order_calls", 0),
        ("review_equity_order_calls", 2),
        ("get_equity_orders_calls", 1),
        ("get_equity_quotes_calls", 1),
        ("paper_record_count", 1),
        ("replay", True),
        ("interactive_reauth_count", 1),
        ("placement_calls", 1),
        ("cancellation_calls", 1),
        ("options_mutation_calls", 1),
        ("crypto_mutation_calls", 1),
        ("review_echo_validated", False),
        ("quote_fill_validated", False),
        ("disclosure_present", False),
    ],
)
def test_rejects_operator_evidence_drift(tmp_path, field, value):
    store, evidence, summary = _fixture(tmp_path)
    operator = _operator()
    operator[field] = value
    evidence.write_text(json.dumps(operator), encoding="utf-8")

    with pytest.raises(
        RobinhoodLiveQualificationVerificationError,
        match="operator evidence mismatch",
    ):
        _verify(store, evidence, summary)


@pytest.mark.parametrize(
    "column,value",
    [
        ("symbol", "QQQ"),
        ("side", "SELL"),
        ("desired_quantity", "1"),
        ("approved_quantity", "2"),
        ("risk_outcome", "APPROVED"),
        ("risk_reason_codes", "MAX_POSITION_PERCENT"),
    ],
)
def test_rejects_new_durable_record_drift(tmp_path, column, value):
    store, evidence, summary = _fixture(tmp_path)
    with sqlite3.connect(store) as connection:
        connection.execute(
            f"UPDATE review_fills SET {column} = ? WHERE order_id = ?",
            (value, str(ORDER)),
        )

    with pytest.raises(RobinhoodLiveQualificationVerificationError):
        _verify(store, evidence, summary)


@pytest.mark.parametrize(
    "column,value",
    [
        ("desired_quantity", "2"),
        ("approved_quantity", "2"),
        ("risk_outcome", "RESIZED"),
        ("risk_reason_codes", "MAX_POSITION_PERCENT"),
        ("fill_price", "769.86"),
        ("commission", "0.01"),
        ("filled_at", "2026-10-03T00:00:01+00:00"),
    ],
)
def test_rejects_prior_durable_record_drift(tmp_path, column, value):
    store, evidence, summary = _fixture(tmp_path)
    with sqlite3.connect(store) as connection:
        connection.execute(
            f"UPDATE review_fills SET {column} = ? WHERE order_id = ?",
            (value, str(PRIOR_ORDER)),
        )

    with pytest.raises(RobinhoodLiveQualificationVerificationError):
        _verify(store, evidence, summary)


def test_rejects_extra_durable_record(tmp_path):
    store, evidence, summary = _fixture(tmp_path)
    with sqlite3.connect(store) as connection:
        connection.execute(
            """
            INSERT INTO review_fills (
                paper_trade_id, order_id, symbol, side, desired_quantity,
                approved_quantity, risk_outcome, risk_reason_codes, fill_price,
                commission, filled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "extra",
                "33333333-131b-4000-8000-000000000001",
                "SPY",
                "BUY",
                "1",
                "1",
                "APPROVED",
                "",
                "770",
                "0",
                "2026-10-05T15:00:00+00:00",
            ),
        )

    with pytest.raises(
        RobinhoodLiveQualificationVerificationError,
        match="exactly two durable",
    ):
        _verify(store, evidence, summary)


def test_rejects_summary_disagreement(tmp_path):
    store, evidence, summary = _fixture(tmp_path)
    value = _summary(store, evidence)
    value["decision"]["approved_quantity"] = "2"
    summary.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(
        RobinhoodLiveQualificationVerificationError,
        match="summary approved quantity mismatch",
    ):
        _verify(store, evidence, summary)


@pytest.mark.parametrize(
    "field,value",
    [
        ("branch", "feature/other"),
        ("proposal_id", "11111111-131b-4000-8000-000000000002"),
        ("qualification_mark", "769.640000"),
    ],
)
def test_rejects_frozen_summary_identity_drift(tmp_path, field, value):
    store, evidence, summary = _fixture(tmp_path)
    document = _summary(store, evidence)
    document[field] = value
    summary.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RobinhoodLiveQualificationVerificationError):
        _verify(store, evidence, summary)


@pytest.mark.parametrize(
    "head,tree",
    [
        ("A" * 40, TREE),
        ("a" * 39, TREE),
        (HEAD, "z" * 40),
    ],
)
def test_rejects_malformed_expected_source_identity(tmp_path, head, tree):
    store, evidence, summary = _fixture(tmp_path)

    with pytest.raises(ValueError):
        verify_robinhood_131l_live_qualification(
            store_path=store,
            operator_evidence_path=evidence,
            summary_path=summary,
            expected_source_head=head,
            expected_source_tree=tree,
            expected_prior_order_id=PRIOR_ORDER,
            expected_order_id=ORDER,
        )


def test_cli_emits_sanitized_pass_json(tmp_path, capsys):
    store, evidence, summary = _fixture(tmp_path)

    exit_code = main(
        [
            "--store",
            str(store),
            "--operator-evidence",
            str(evidence),
            "--summary",
            str(summary),
            "--expected-head",
            HEAD,
            "--expected-tree",
            TREE,
            "--prior-order-id",
            str(PRIOR_ORDER),
            "--order-id",
            str(ORDER),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["record_count"] == 2
    assert payload["position_quantity"] == "2.000"
    assert payload["order_id"] == str(ORDER)
