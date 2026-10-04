"""Independent fixture evidence and SQLite; no provider/store runtime imports."""

import ast
import copy
import hashlib
import json
import sqlite3
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.robinhood_prepare_qualification_verifier as module

AT = datetime(2026, 10, 2, 16, tzinfo=UTC)
HEAD = "a" * 40
TREE = "b" * 40
PROPOSAL = UUID(int=1)
ERROR = module.RobinhoodPrepareQualificationVerificationError


def _fingerprint(path):
    with sqlite3.connect(path) as connection:
        metadata = connection.execute(
            "SELECT key, value FROM metadata ORDER BY key"
        ).fetchall()
        cursor = connection.execute(
            "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
        )
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchall()
    material = {
        "metadata": metadata,
        "columns": columns,
        "rows": rows,
        "record_count": len(rows),
    }
    return {
        "metadata": [list(row) for row in metadata],
        "record_count": len(rows),
        "sha256": hashlib.sha256(
            json.dumps(
                material, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest(),
    }


def _admission(status="ADMITTED", at=AT):
    return {
        "status": status,
        "as_of": at.isoformat(),
        "session_date": AT.date().isoformat(),
        "opens_at": AT.replace(hour=13, minute=30).isoformat(),
        "closes_at": AT.replace(hour=20).isoformat(),
        "admission_opens_at": AT.replace(hour=13, minute=35).isoformat(),
        "admission_closes_at": AT.replace(hour=19, minute=55).isoformat(),
    }


@pytest.fixture
def h(tmp_path):
    store = tmp_path / "paper.sqlite"
    with sqlite3.connect(store) as connection:
        connection.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [("starting_cash", "10000"), ("schema_version", "2")],
        )
        connection.execute(
            "CREATE TABLE review_fills (paper_trade_id TEXT PRIMARY KEY, "
            "filled_at TEXT, arbitrary_extra_column TEXT)"
        )
        connection.execute(
            "INSERT INTO review_fills VALUES ('fixture', ?, 'full column coverage')",
            (AT.isoformat(),),
        )
    durable = _fingerprint(store)
    evidence = {
        "schema": "arch131-q-prepare-qualification/v1",
        "source_head": HEAD,
        "source_tree": TREE,
        "store_path": str(store),
        "starting_cash": "10000",
        "proposal": {
            "proposal_id": str(PROPOSAL),
            "symbol": "SPY",
            "side": "BUY",
            "desired_quantity": "1.000",
            "created_at": AT.isoformat(),
        },
        "schedule": {
            "session_date": AT.date().isoformat(),
            "opens_at": AT.replace(hour=13, minute=30).isoformat(),
            "closes_at": AT.replace(hour=20).isoformat(),
        },
        "opening_buffer_seconds": 300.0,
        "closing_buffer_seconds": 300.0,
        "max_quote_age_seconds": 60.000001,
        "new_trading_enabled": True,
        "durable_before": copy.deepcopy(durable),
        "durable_after": copy.deepcopy(durable),
        "preparation": {
            "status": "READY_TO_PROCEED",
            "initial_admission": _admission(),
            "quote_admission": _admission(),
            "price_snapshot": {
                "observed_at": AT.isoformat(),
                "marks": [
                    {
                        "symbol": "AAPL",
                        "price": "100.123400",
                        "source_at": (AT - timedelta(microseconds=1)).isoformat(),
                    },
                    {"symbol": "SPY", "price": "100.00", "source_at": AT.isoformat()},
                ],
            },
            "risk_preview": {
                "requested_quantity": "1.000",
                "risk_outcome": "APPROVED",
                "approved_quantity": "1.000",
                "reason_codes": [],
                "cash": "10000",
                "equity": "10000",
                "current_price": "100.00",
                "total_market_exposure": "0",
                "current_position_quantity": "0",
                "current_position_market_value": "0",
                "projected_position_quantity": "1.000",
                "projected_position_market_value": "100.00000",
                "projected_total_market_exposure": "100.00000",
            },
            "quote_valid_until": (AT + timedelta(seconds=60)).isoformat(),
        },
        "execute_invoked": False,
        "pipeline_result_present": False,
    }
    return SimpleNamespace(
        store=store, path=tmp_path / "evidence.json", evidence=evidence
    )


def _verify(h, **changes):
    h.path.write_text(json.dumps(h.evidence), encoding="utf-8")
    return module.verify_robinhood_prepare_qualification(
        **{
            "store_path": h.store,
            "evidence_path": h.path,
            "expected_source_head": HEAD,
            "expected_source_tree": TREE,
            "expected_proposal_id": PROPOSAL,
            **changes,
        }
    )


def _state(h, status):
    p = h.evidence["preparation"]
    p["status"] = status
    if status == "SESSION_NOT_ADMITTED":
        p["initial_admission"] = _admission(
            "OPENING_BUFFER", AT.replace(hour=13, minute=30)
        )
        for field in (
            "price_snapshot",
            "quote_admission",
            "risk_preview",
            "quote_valid_until",
        ):
            p[field] = None
    elif status == "SESSION_EXPIRED_DURING_ACQUISITION":
        observed = AT.replace(hour=20)
        p["price_snapshot"]["observed_at"] = observed.isoformat()
        p["quote_admission"] = _admission("AFTER_REGULAR_WINDOW", observed)
        p["risk_preview"] = p["quote_valid_until"] = None
    elif status == "RISK_REJECTED":
        p["risk_preview"]["risk_outcome"] = "REJECTED"
        p["risk_preview"]["approved_quantity"] = "0"
        p["risk_preview"]["reason_codes"] = ["NEW_TRADING_DISABLED"]


@pytest.mark.parametrize(
    "status",
    [
        "SESSION_NOT_ADMITTED",
        "SESSION_EXPIRED_DURING_ACQUISITION",
        "RISK_REJECTED",
        "READY_TO_PROCEED",
    ],
)
def test_valid_status_passes_readonly_and_immutable(h, status, monkeypatch):
    _state(h, status)
    before = h.store.read_bytes()
    connect = sqlite3.connect
    calls = []

    def readonly(database, **kwargs):
        assert (
            database.startswith("file:")
            and database.endswith("?mode=ro")
            and kwargs == {"uri": True}
        )
        connection = connect(database, **kwargs)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM metadata")
        connection.rollback()
        calls.append(database)
        return connection

    monkeypatch.setattr(module.sqlite3, "connect", readonly)
    result = _verify(h)
    assert len(calls) == 1
    assert result.preparation_status == status and result.record_count == 1
    assert result.durable_sha256 == h.evidence["durable_before"]["sha256"]
    assert (
        result.proposal_id == PROPOSAL
        and result.source_head == HEAD
        and result.source_tree == TREE
    )
    assert h.store.read_bytes() == before
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.record_count = 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("store_path", Path("relative.sqlite")),
        ("evidence_path", Path("relative.json")),
        ("store_path", "string"),
        ("evidence_path", "string"),
        ("expected_source_head", "A" * 40),
        ("expected_source_tree", "g" * 40),
        ("expected_source_head", "a" * 39),
        ("expected_source_tree", 1),
        ("expected_proposal_id", str(PROPOSAL)),
    ],
)
def test_input_admission(h, key, value):
    with pytest.raises((ValueError, TypeError)):
        _verify(h, **{key: value})


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", "wrong"),
        ("source_head", "c" * 40),
        ("source_tree", "c" * 40),
        ("store_path", "relative.sqlite"),
        ("store_path", "C:/wrong.sqlite"),
        ("execute_invoked", True),
        ("execute_invoked", 0),
        ("pipeline_result_present", True),
        ("pipeline_result_present", 0),
        ("starting_cash", "9999"),
        ("new_trading_enabled", 1),
        ("max_quote_age_seconds", 0),
        ("max_quote_age_seconds", -1),
        ("max_quote_age_seconds", 0.0000001),
        ("max_quote_age_seconds", True),
    ],
)
def test_evidence_identity_and_flags(h, key, value):
    h.evidence[key] = value
    with pytest.raises(ERROR):
        _verify(h)


def test_proposal_mismatch(h):
    with pytest.raises(ERROR, match="proposal"):
        _verify(h, expected_proposal_id=UUID(int=2))


@pytest.mark.parametrize("section", ["durable_before", "durable_after"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("metadata", [["wrong", "value"]]),
        ("record_count", 2),
        ("record_count", True),
        ("sha256", "c" * 64),
    ],
)
def test_before_after_mismatches(h, section, field, value):
    h.evidence[section][field] = value
    with pytest.raises(ERROR):
        _verify(h)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE review_fills SET arbitrary_extra_column='tamper'",
        "UPDATE metadata SET value='9999' WHERE key='starting_cash'",
        "INSERT INTO review_fills VALUES ('second', 'later', 'row drift')",
        "ALTER TABLE review_fills ADD COLUMN newly_persisted TEXT",
    ],
)
def test_current_durable_drift(h, sql):
    with sqlite3.connect(h.store) as connection:
        connection.execute(sql)
    with pytest.raises(ERROR, match="durable state"):
        _verify(h)


@pytest.mark.parametrize(
    "status,field,value",
    [
        ("SESSION_NOT_ADMITTED", "initial_admission", "admitted"),
        *[
            ("SESSION_NOT_ADMITTED", field, "present")
            for field in (
                "price_snapshot",
                "quote_admission",
                "risk_preview",
                "quote_valid_until",
            )
        ],
        ("SESSION_EXPIRED_DURING_ACQUISITION", "initial_admission", "blocked"),
        ("SESSION_EXPIRED_DURING_ACQUISITION", "price_snapshot", None),
        ("SESSION_EXPIRED_DURING_ACQUISITION", "quote_admission", None),
        ("SESSION_EXPIRED_DURING_ACQUISITION", "quote_admission", "admitted"),
        ("SESSION_EXPIRED_DURING_ACQUISITION", "risk_preview", "present"),
        ("SESSION_EXPIRED_DURING_ACQUISITION", "quote_valid_until", "present"),
        *[
            (status, field, None)
            for status in ("RISK_REJECTED", "READY_TO_PROCEED")
            for field in (
                "price_snapshot",
                "quote_admission",
                "risk_preview",
                "quote_valid_until",
            )
        ],
        *[
            (status, field, "blocked")
            for status in ("RISK_REJECTED", "READY_TO_PROCEED")
            for field in ("initial_admission", "quote_admission")
        ],
    ],
)
def test_optional_field_invariants(h, status, field, value):
    original = copy.deepcopy(h.evidence["preparation"])
    _state(h, status)
    if value == "admitted":
        value = _admission()
    elif value == "blocked":
        value = _admission("OPENING_BUFFER", AT.replace(hour=13, minute=30))
    elif value == "present":
        value = original[field]
    h.evidence["preparation"][field] = value
    with pytest.raises(ERROR):
        _verify(h)


@pytest.mark.parametrize(
    "change",
    [
        "empty",
        "not_list",
        "duplicate",
        "unsorted",
        "not_object",
        "symbol_type",
        "symbol_blank",
        "symbol_lower",
        "extra",
        "missing_price",
    ],
)
def test_malformed_noncanonical_marks(h, change):
    marks = h.evidence["preparation"]["price_snapshot"]["marks"]
    if change == "empty":
        marks.clear()
    elif change == "not_list":
        h.evidence["preparation"]["price_snapshot"]["marks"] = {}
    elif change == "duplicate":
        marks.append(copy.deepcopy(marks[0]))
    elif change == "unsorted":
        marks.reverse()
    elif change == "not_object":
        marks[0] = None
    elif change == "extra":
        marks[0]["raw_provider"] = "forbidden"
    elif change == "missing_price":
        del marks[0]["price"]
    else:
        marks[0]["symbol"] = {
            "symbol_type": 1,
            "symbol_blank": "",
            "symbol_lower": "aapl",
        }[change]
    with pytest.raises(ERROR):
        _verify(h)


@pytest.mark.parametrize(
    "price", ["0", "-1", "NaN", "sNaN", "Infinity", "-Infinity", "bad", 100, None]
)
def test_invalid_mark_prices(h, price):
    h.evidence["preparation"]["price_snapshot"]["marks"][0]["price"] = price
    with pytest.raises(ERROR):
        _verify(h)


@pytest.mark.parametrize("field", ["observed_at", "source_at"])
@pytest.mark.parametrize("value", ["2026-10-02T16:00:00", "bad", 1])
def test_quote_timestamps_must_be_aware(h, field, value):
    snapshot = h.evidence["preparation"]["price_snapshot"]
    (snapshot if field == "observed_at" else snapshot["marks"][0])[field] = value
    with pytest.raises(ERROR):
        _verify(h)


def test_future_source_timestamp(h):
    h.evidence["preparation"]["price_snapshot"]["marks"][0]["source_at"] = (
        AT + timedelta(microseconds=1)
    ).isoformat()
    with pytest.raises(ERROR, match="future"):
        _verify(h)


@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_exact_earliest_deadline(h, microseconds):
    h.evidence["preparation"]["quote_valid_until"] = (
        AT + timedelta(seconds=60, microseconds=microseconds)
    ).isoformat()
    if microseconds:
        with pytest.raises(ERROR, match="deadline"):
            _verify(h)
    else:
        result = _verify(h)
        assert result.quote_valid_until == AT + timedelta(seconds=60)
        assert result.approved_quantity == Decimal("1.000")


def test_deadline_overflow_fail_closed(h):
    h.evidence["max_quote_age_seconds"] = timedelta.max.days * 86400
    with pytest.raises(ERROR) as caught:
        _verify(h)
    assert isinstance(caught.value.__cause__, OverflowError)


@pytest.mark.parametrize(
    "status,outcome,quantity",
    [
        ("RISK_REJECTED", "APPROVED", "0"),
        ("RISK_REJECTED", "REJECTED", "1"),
        ("READY_TO_PROCEED", "REJECTED", "0"),
        ("READY_TO_PROCEED", "RESIZED", "0"),
        ("READY_TO_PROCEED", "APPROVED", "-1"),
        ("READY_TO_PROCEED", "UNKNOWN", "1"),
        ("READY_TO_PROCEED", "APPROVED", "NaN"),
    ],
)
def test_risk_status_outcome_quantity_mismatch(h, status, outcome, quantity):
    _state(h, status)
    p = h.evidence["preparation"]["risk_preview"]
    p["risk_outcome"] = outcome
    p["approved_quantity"] = quantity
    with pytest.raises(ERROR):
        _verify(h)


def test_resized_passes(h):
    h.evidence["preparation"]["risk_preview"].update(
        risk_outcome="RESIZED",
        approved_quantity="0.500",
        reason_codes=["MAX_POSITION_PERCENT"],
    )
    assert _verify(h).approved_quantity == Decimal("0.500")


@pytest.mark.parametrize("metadata_change", ["schema_version", "extra_key"])
def test_self_consistent_wrong_metadata_rejected(h, metadata_change):
    with sqlite3.connect(h.store) as connection:
        if metadata_change == "schema_version":
            connection.execute(
                "UPDATE metadata SET value='999' WHERE key='schema_version'"
            )
        else:
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES ('unexpected', 'value')"
            )
    durable = _fingerprint(h.store)
    h.evidence["durable_before"] = copy.deepcopy(durable)
    h.evidence["durable_after"] = copy.deepcopy(durable)
    with pytest.raises(ERROR, match="metadata"):
        _verify(h)


@pytest.mark.parametrize(
    "field,at",
    [
        ("initial_admission", AT.replace(hour=13, minute=30)),
        ("quote_admission", AT.replace(hour=20)),
    ],
)
def test_forged_admitted_status_inconsistent_with_timestamp_rejected(h, field, at):
    h.evidence["preparation"][field] = _admission("ADMITTED", at)
    if field == "quote_admission":
        h.evidence["preparation"]["price_snapshot"]["observed_at"] = at.isoformat()
    with pytest.raises(ERROR, match="status"):
        _verify(h)


def test_completed_preview_rejects_quote_already_stale_at_observation(h):
    stale_source = AT - timedelta(seconds=61)
    h.evidence["preparation"]["price_snapshot"]["marks"][0]["source_at"] = (
        stale_source.isoformat()
    )
    h.evidence["preparation"]["quote_valid_until"] = (
        stale_source + timedelta(seconds=60, microseconds=1)
    ).isoformat()
    with pytest.raises(ERROR, match="already stale"):
        _verify(h)


def test_cli_pass_deterministic_json(h, capsys):
    _verify(h)
    args = [
        "--store",
        str(h.store),
        "--evidence",
        str(h.path),
        "--expected-head",
        HEAD,
        "--expected-tree",
        TREE,
        "--proposal-id",
        str(PROPOSAL),
    ]
    assert module.main(args) == 0
    first = capsys.readouterr().out
    assert module.main(args) == 0
    assert first == capsys.readouterr().out
    payload = json.loads(first)
    assert payload["status"] == "PASS"
    assert payload["approved_quantity"] == "1.000"
    assert payload["quote_valid_until"] == (AT + timedelta(seconds=60)).isoformat()
    assert payload["proposal_id"] == str(PROPOSAL)


def test_missing_files_never_create_store(h):
    missing = h.store.parent / "missing.sqlite"
    with pytest.raises(ERROR):
        _verify(h, store_path=missing)
    assert not missing.exists()
    h.path.write_text("invalid JSON")
    with pytest.raises(ERROR):
        module.verify_robinhood_prepare_qualification(
            store_path=h.store,
            evidence_path=h.path,
            expected_source_head=HEAD,
            expected_source_tree=TREE,
            expected_proposal_id=PROPOSAL,
        )


def test_duplicate_json_keys_rejected(h):
    _verify(h)
    source = h.path.read_text()
    h.path.write_text(
        source.replace(
            '"execute_invoked": false',
            '"execute_invoked": true, "execute_invoked": false',
        )
    )
    with pytest.raises(ERROR, match="duplicate"):
        module.verify_robinhood_prepare_qualification(
            store_path=h.store,
            evidence_path=h.path,
            expected_source_head=HEAD,
            expected_source_tree=TREE,
            expected_proposal_id=PROPOSAL,
        )


def test_structural_no_provider_store_risk_execution_capability():
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "argparse",
        "hashlib",
        "json",
        "re",
        "sqlite3",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "pathlib",
        "uuid",
        "zoneinfo",
        "trading_bot.review_paper.nyse_published_regular_sessions",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed
        elif isinstance(node, ast.Import):
            assert all(alias.name in allowed for alias in node.names)
    forbidden = {
        "ReviewPaperStore",
        "RobinhoodReviewReadAdapter",
        "RiskManager",
        "prepare_review_paper_supervised_cycle",
        "execute_review_paper_supervised_cycle",
        "ExecutionInstruction",
        "sleep",
        "subprocess",
        "socket",
        "os",
    }
    assert not forbidden.intersection(
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    )
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
        ):
            assert all(
                not isinstance(arg, ast.Constant) or arg.value in {"r", "rb"}
                for arg in node.args
            )
    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in {"write", "write_text", "write_bytes", "mkdir", "unlink"}
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize("symbol", ["1ST", "BRK.B", "ABC-DEF"])
def test_canonical_symbol_matches_accepted_domain_alphabet(h, symbol):
    h.evidence["proposal"]["symbol"] = symbol
    marks = h.evidence["preparation"]["price_snapshot"]["marks"]
    marks[0]["symbol"] = symbol
    marks.sort(key=lambda mark: mark["symbol"])
    assert _verify(h).preparation_status == "READY_TO_PROCEED"


def test_overlength_symbol_rejected(h):
    h.evidence["preparation"]["price_snapshot"]["marks"][0]["symbol"] = "ABCDEFGHIJK"
    with pytest.raises(ERROR, match="symbol"):
        _verify(h)


# Self-consistent blocked evidence isolates schedule provenance from later checks.
def _published_schedule_evidence(h, session_date, open_hour, close_hour):
    opens = datetime.fromisoformat(session_date + "T00:00:00+00:00").replace(
        hour=open_hour, minute=30
    )
    closes = opens.replace(hour=close_hour, minute=0)
    schedule = dict(
        session_date=session_date,
        opens_at=opens.isoformat(),
        closes_at=closes.isoformat(),
    )
    h.evidence["schedule"] = schedule
    preparation = h.evidence["preparation"]
    preparation.update(
        status="SESSION_NOT_ADMITTED",
        initial_admission={
            **schedule,
            "status": "BEFORE_REGULAR_WINDOW",
            "as_of": (opens - timedelta(minutes=1)).isoformat(),
            "admission_opens_at": (opens + timedelta(minutes=5)).isoformat(),
            "admission_closes_at": (closes - timedelta(minutes=5)).isoformat(),
        },
        price_snapshot=None,
        quote_admission=None,
        risk_preview=None,
        quote_valid_until=None,
    )


@pytest.mark.parametrize(
    "session_date,open_hour,close_hour",
    [
        ("2026-01-05", 14, 21),
        ("2026-07-06", 13, 20),
        ("2026-11-27", 14, 18),
    ],
)
def test_canonical_published_schedule_passes_readonly(
    h, session_date, open_hour, close_hour, monkeypatch
):
    _published_schedule_evidence(h, session_date, open_hour, close_hour)
    before = h.store.read_bytes()
    authority = module.NYSEPublishedRegularSessionAuthority
    original = authority.schedule_for
    calls = []

    def resolve(self, value):
        calls.append(value)
        return original(self, value)

    monkeypatch.setattr(authority, "schedule_for", resolve)
    assert _verify(h).preparation_status == "SESSION_NOT_ADMITTED"
    assert [value.isoformat() for value in calls] == [session_date]
    assert h.store.read_bytes() == before


@pytest.mark.parametrize(
    "session_date,open_hour,close_hour",
    [
        ("2026-10-02", 14, 20),  # fabricated ordinary open
        ("2026-10-02", 13, 21),  # fabricated ordinary close
        ("2026-11-27", 14, 21),  # missing published early close
        ("2026-10-02", 13, 17),  # invented early close
        ("2026-10-03", 13, 20),  # weekend
        ("2026-12-25", 14, 21),  # published holiday
        ("2029-01-02", 14, 21),  # unsupported manifest year
    ],
)
def test_schedule_provenance_rejects_before_store_read(
    h, session_date, open_hour, close_hour, monkeypatch
):
    _published_schedule_evidence(h, session_date, open_hour, close_hour)

    def forbidden_read(*args):
        pytest.fail("invalid schedule must fail before durable read")

    monkeypatch.setattr(module, "_read_current", forbidden_read)
    before = h.store.read_bytes()
    with pytest.raises(ERROR):
        _verify(h)
    assert h.store.read_bytes() == before
