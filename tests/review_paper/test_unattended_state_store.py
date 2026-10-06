"""133-B local durability and independent read-only reconciliation contracts."""

import ast
import hashlib
import json
import sqlite3
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest

import trading_bot.review_paper.unattended_state_store as writer
import trading_bot.review_paper.unattended_state_verifier as verifier
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWake,
)
from trading_bot.review_paper.unattended_activation import (
    ReviewPaperWakeState as State,
)
from trading_bot.review_paper.unattended_state_schema import (
    MAX_REVISION,
    PersistedReviewPaperWake,
    UnattendedStateConflict,
    UnattendedStateError,
)
from trading_bot.risk.models import RiskLimits

AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def activation():
    return ReviewPaperActivation(
        source_head="a" * 40,
        source_tree="b" * 40,
        deployment_identity="c" * 64,
        target_session_date=date(2026, 10, 5),
        proposal=TradeProposal(
            proposal_id=UUID("11111111-131c-4000-8000-000000000002"),
            symbol=Symbol("SPY"),
            side=OrderSide.SELL,
            desired_quantity=Decimal("1"),
            created_at=AT,
            reason="frozen proposal 雪",
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID("33333333-131c-4000-8000-000000000001"),
        store_path=r"F:\AITradingBot\paper\never-open.sqlite",
        starting_cash=Decimal("10000"),
        opening_buffer=timedelta(minutes=15),
        closing_buffer=timedelta(minutes=15),
        max_quote_age=timedelta(minutes=5),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0"),
        local_order_id=UUID("22222222-131c-4000-8000-000000000001"),
        created_at=AT,
    )


@pytest.fixture
def store(tmp_path):
    return writer.UnattendedStateStore(tmp_path / "wake.sqlite")


def _verify(store, activation, current=None):
    wake = (
        current.wake
        if current
        else ReviewPaperWake(activation=activation, updated_at=AT)
    )
    return verifier.verify_unattended_state(
        store.path,
        expected_activation=activation,
        expected_wake_id=wake.wake_id,
        expected_wake=current.wake if current else None,
        expected_revision=current.revision if current else None,
    )


def _sql(store, sql, values=()):
    with sqlite3.connect(store.path) as connection:
        connection.execute(sql, values)


def test_atomic_admission_canonical_rows_and_exact_readonly_reopen(
    store, activation, monkeypatch
):
    assert not store.path.exists()
    current = store.admit(activation)
    assert current == PersistedReviewPaperWake(
        ReviewPaperWake(activation=activation, updated_at=AT), 0
    )
    before = store.path.read_bytes()
    snapshot = store.snapshot()
    assert snapshot.activations == (
        (str(activation.activation_id), activation.to_json()),
    )
    assert snapshot.wakes == (
        (
            str(activation.activation_id),
            str(current.wake.wake_id),
            current.wake.to_json(),
            0,
        ),
    )
    assert (
        snapshot.fingerprint == hashlib.sha256(snapshot.to_json().encode()).hexdigest()
    )
    statements = []
    real = sqlite3.connect

    def readonly_connect(database, **kwargs):
        assert database.endswith("?mode=ro") and kwargs["uri"] is True
        connection = real(database, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(writer.sqlite3, "connect", readonly_connect)
    assert writer.UnattendedStateStore(store.path).admit(activation) == current
    assert store.path.read_bytes() == before
    assert all(
        sql == "BEGIN"
        or sql.startswith(("SELECT", "PRAGMA application_id", "PRAGMA user_version"))
        for sql in statements
    )
    assert not any(
        word in " ".join(statements)
        for word in ("INSERT", "UPDATE", "CREATE", "DELETE")
    )


def test_same_id_changed_path_conflicts_without_any_write(store, activation):
    store.admit(activation)
    changed = replace(activation, store_path=r"F:\AITradingBot\paper\changed.sqlite")
    assert changed.activation_id == activation.activation_id
    assert changed.to_json() != activation.to_json()
    before = store.path.read_bytes()
    with pytest.raises(UnattendedStateConflict):
        store.admit(changed)
    with pytest.raises(UnattendedStateConflict):
        _verify(store, changed)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize(
    "states",
    [
        [State.PREPARE_STARTED],
        [State.PREPARE_STARTED, State.PREPARED],
        [State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED],
        [State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED, State.COMPLETED],
        [
            State.PREPARE_STARTED,
            State.PREPARED,
            State.REVIEW_STARTED,
            State.INDETERMINATE,
        ],
        [State.STOPPED],
        [State.PREPARE_STARTED, State.STOPPED],
        [State.PREPARE_STARTED, State.PREPARED, State.STOPPED],
    ],
)
def test_legal_transition_exact_durability_and_delegation(
    store, activation, states, monkeypatch
):
    calls = []
    real = writer.transition_review_paper_wake

    def transition(wake, **kwargs):
        calls.append((wake, kwargs))
        return real(wake, **kwargs)

    monkeypatch.setattr(writer, "transition_review_paper_wake", transition)
    current = store.admit(activation)
    for index, state in enumerate(states, 1):
        previous = current
        at = AT + timedelta(seconds=index)
        current = store.transition(previous, state=state, at=at)
        assert current.wake == real(previous.wake, state=state, at=at)
        assert current.revision == index
        reopened = writer.UnattendedStateStore(store.path)
        assert reopened.admit(activation) == current
        result = _verify(reopened, activation, current)
        assert result.state == state and result.revision == index
    assert len(calls) == len(states)


@pytest.mark.parametrize(
    "terminal", [State.COMPLETED, State.STOPPED, State.INDETERMINATE]
)
@pytest.mark.parametrize("target", list(State))
def test_terminal_reopen_grants_no_transition(store, activation, terminal, target):
    states = (
        [State.STOPPED]
        if terminal == State.STOPPED
        else [State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED, terminal]
    )
    current = store.admit(activation)
    for state in states:
        current = store.transition(current, state=state, at=AT)
    reopened = writer.UnattendedStateStore(store.path)
    current = reopened.admit(activation)
    before = reopened.snapshot()
    with pytest.raises(ValueError, match="illegal wake transition"):
        reopened.transition(current, state=target, at=AT)
    assert reopened.snapshot() == before


def test_stale_writer_exact_cas_conflicting_wake_and_revision(store, activation):
    current = store.admit(activation)
    other = writer.UnattendedStateStore(store.path)
    current2 = other.transition(current, state=State.PREPARE_STARTED, at=AT)
    before = store.snapshot()
    for stale in (
        current,
        replace(current2, revision=0),
        replace(
            current2, wake=replace(current2.wake, updated_at=AT + timedelta(seconds=1))
        ),
        replace(
            current2,
            wake=replace(
                current2.wake,
                activation=replace(activation, store_path=r"F:\Other\paper.sqlite"),
            ),
        ),
    ):
        with pytest.raises(UnattendedStateConflict):
            store.transition(stale, state=State.PREPARED, at=AT + timedelta(seconds=2))
        assert store.snapshot() == before


@pytest.mark.parametrize(
    "failure_point", ["INSERT INTO activations", "INSERT INTO wakes", "UPDATE wakes"]
)
def test_sql_failure_rolls_back_whole_transaction(
    store, activation, monkeypatch, failure_point
):
    current = store.admit(activation)
    before = store.snapshot()
    candidate = replace(activation, deployment_identity="d" * 64)
    real = sqlite3.connect
    writes = []

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith(("INSERT", "UPDATE")):
                writes.append(sql)
            if sql.startswith(failure_point):
                raise sqlite3.OperationalError("injected secret path error")
            return super().execute(sql, parameters)

    def connect(path, **kwargs):
        return real(path, factory=FailingConnection, **kwargs)

    monkeypatch.setattr(writer.sqlite3, "connect", connect)
    with pytest.raises(UnattendedStateError, match="without retry") as caught:
        if failure_point.startswith("UPDATE"):
            store.transition(current, state=State.PREPARE_STARTED, at=AT)
        else:
            store.admit(candidate)
    assert "secret" not in str(caught.value)
    assert store.snapshot() == before
    assert len([sql for sql in writes if sql.startswith(failure_point)]) == 1


def test_first_admission_schema_and_rows_rollback(store, activation, monkeypatch):
    real = sqlite3.connect

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith("INSERT INTO wakes"):
                raise sqlite3.OperationalError("injected")
            return super().execute(sql, parameters)

    monkeypatch.setattr(
        writer.sqlite3,
        "connect",
        lambda path, **kwargs: real(path, factory=FailingConnection, **kwargs),
    )
    with pytest.raises(UnattendedStateError):
        store.admit(activation)
    with real(store.path) as connection:
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
        assert connection.execute("PRAGMA application_id").fetchone() == (0,)
    with pytest.raises(UnattendedStateError):
        store.admit(activation)  # existing partial/empty files cannot be repaired


@pytest.mark.parametrize(
    "sql,parameters",
    [
        ("PRAGMA user_version=2", ()),
        ("PRAGMA application_id=7", ()),
        ("CREATE TABLE surprise (value TEXT)", ()),
        ("CREATE VIEW surprise AS SELECT * FROM wakes", ()),
        ("CREATE INDEX surprise ON wakes(revision)", ()),
        (
            "CREATE TRIGGER surprise AFTER UPDATE ON wakes "
            "BEGIN DELETE FROM metadata; END",
            (),
        ),
        ("DROP TABLE wakes", ()),
        ("DELETE FROM metadata", ()),
        ("INSERT INTO metadata VALUES ('extra','secret')", ()),
        ("UPDATE metadata SET value='2' WHERE key='version'", ()),
        ("DELETE FROM wakes", ()),
        ("DELETE FROM activations", ()),
        ("UPDATE activations SET activation_id='wrong'", ()),
        ("UPDATE activations SET activation_json='{}'", ()),
        ("UPDATE activations SET activation_json=activation_json || ' '", ()),
        ("UPDATE wakes SET wake_json='{}'", ()),
        ("UPDATE wakes SET wake_json=wake_json || ' '", ()),
        ("UPDATE wakes SET wake_id='wrong'", ()),
        ("UPDATE wakes SET activation_id='wrong'", ()),
        ("UPDATE wakes SET revision=1.5", ()),
        ("UPDATE wakes SET revision='wrong'", ()),
        ("UPDATE wakes SET revision=?", (sqlite3.Binary(b"wrong"),)),
    ],
)
def test_malformed_schema_metadata_and_rows_fail_closed_without_repair(
    store, activation, sql, parameters
):
    current = store.admit(activation)
    _sql(store, sql, parameters)
    before = store.path.read_bytes()
    with pytest.raises(UnattendedStateError):
        _verify(store, activation)
    with pytest.raises(UnattendedStateError):
        store.admit(activation)
    with pytest.raises(UnattendedStateError):
        store.transition(current, state=State.PREPARE_STARTED, at=AT)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("activation_id", "11111111-1111-5111-8111-111111111111"),
        ("wake_id", "11111111-1111-5111-8111-111111111111"),
        ("proposal_id", "11111111-1111-5111-8111-111111111111"),
        ("local_order_id", "11111111-1111-5111-8111-111111111111"),
        ("target_session_date", "2026-10-06"),
        ("state", "UNKNOWN"),
    ],
)
def test_wake_canonical_binding_mismatch(store, activation, field, value):
    current = store.admit(activation)
    payload = json.loads(current.wake.to_json())
    payload[field] = value
    _sql(
        store,
        "UPDATE wakes SET wake_json=?",
        (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
    )
    with pytest.raises(UnattendedStateError):
        _verify(store, activation)


def test_conflicting_activation_canonical_identity_material(store, activation):
    store.admit(activation)
    changed = replace(activation, deployment_identity="d" * 64)
    _sql(store, "UPDATE activations SET activation_json=?", (changed.to_json(),))
    with pytest.raises(UnattendedStateError):
        _verify(store, activation)


@pytest.mark.parametrize("revision", [True, -1, 1.5, "0", MAX_REVISION, None])
def test_invalid_expected_cas_revision_rejected(store, activation, revision):
    current = store.admit(activation)
    before = store.snapshot()
    with pytest.raises(UnattendedStateError):
        store.transition(
            replace(current, revision=revision), state=State.STOPPED, at=AT
        )
    assert store.snapshot() == before


def test_revision_exhaustion_never_wraps(store, activation):
    store.admit(activation)
    _sql(store, "UPDATE wakes SET revision=?", (MAX_REVISION,))
    current = store.admit(activation)
    with pytest.raises(UnattendedStateError):
        store.transition(current, state=State.STOPPED, at=AT)
    assert store.admit(activation) == current


def test_complete_fingerprint_sorted_rows_transport_and_ambient_independence(
    store, activation, tmp_path, monkeypatch
):
    first = store.admit(activation)
    second_activation = replace(activation, deployment_identity="d" * 64)
    second = store.admit(second_activation)
    snapshot = store.snapshot()
    assert len(snapshot.activations) == len(snapshot.wakes) == 2
    assert (
        snapshot.fingerprint
        == replace(
            snapshot,
            metadata=tuple(reversed(snapshot.metadata)),
            activations=tuple(reversed(snapshot.activations)),
            wakes=tuple(reversed(snapshot.wakes)),
        ).fingerprint
    )
    copied = tmp_path / "different transport 雪.sqlite"
    copied.write_bytes(store.path.read_bytes())
    assert verifier.snapshot_unattended_state(copied) == snapshot
    real = sqlite3.connect

    def reversed_rows(database, **kwargs):
        connection = real(database, **kwargs)
        connection.execute("PRAGMA reverse_unordered_selects=ON")
        return connection

    monkeypatch.setattr(verifier.sqlite3, "connect", reversed_rows)
    with localcontext() as context:
        context.prec = 2
        assert store.snapshot().fingerprint == snapshot.fingerprint
    store.transition(second, state=State.STOPPED, at=AT)
    assert _verify(store, activation, first).fingerprint != snapshot.fingerprint
    assert _verify(store, activation, first).activation_count == 2


def test_verifier_result_is_frozen_slotted_bounded_sanitized(store, activation):
    current = store.admit(activation)
    result = _verify(store, activation, current)
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.revision = 3
    assert str(activation.store_path) not in repr(result)
    assert activation.proposal.reason not in repr(result)
    assert str(store.path) not in repr(result)
    assert len(result.fingerprint) == 64


@pytest.mark.parametrize("change", ["wake_id", "wake", "revision", "path_activation"])
def test_verifier_expected_state_mismatch(store, activation, change):
    current = store.admit(activation)
    kwargs = dict(
        expected_activation=activation,
        expected_wake_id=current.wake.wake_id,
        expected_wake=current.wake,
        expected_revision=0,
    )
    if change == "wake_id":
        kwargs["expected_wake_id"] = UUID("11111111-1111-5111-8111-111111111111")
    elif change == "wake":
        kwargs["expected_wake"] = replace(
            current.wake, updated_at=AT + timedelta(seconds=1)
        )
    elif change == "revision":
        kwargs["expected_revision"] = 1
    else:
        kwargs["expected_wake"] = replace(
            current.wake,
            activation=replace(activation, store_path=r"F:\Other\paper.sqlite"),
        )
    with pytest.raises(UnattendedStateConflict):
        verifier.verify_unattended_state(store.path, **kwargs)


def test_verifier_is_sqlite_readonly_and_never_constructs_writer(
    store, activation, monkeypatch
):
    store.admit(activation)
    before = store.path.read_bytes()
    files = set(store.path.parent.iterdir())
    real = sqlite3.connect
    statements = []
    connections = []

    def ro_connect(database, **kwargs):
        assert database == store.path.as_uri() + "?mode=ro"
        assert kwargs == {"uri": True, "timeout": 0}
        connection = real(database, **kwargs)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("UPDATE wakes SET revision=revision+1")
        connection.rollback()
        connection.set_trace_callback(statements.append)
        connections.append(connection)
        return connection

    def forbidden(*args, **kwargs):
        pytest.fail("write/provider/paper/transition surface invoked")

    monkeypatch.setattr(verifier.sqlite3, "connect", ro_connect)
    monkeypatch.setattr(writer.UnattendedStateStore, "__init__", forbidden)
    monkeypatch.setattr(writer, "transition_review_paper_wake", forbidden)
    assert _verify(store, activation).state == State.READY
    assert all(
        sql == "BEGIN"
        or sql.startswith(("SELECT", "PRAGMA application_id", "PRAGMA user_version"))
        for sql in statements
    )
    assert store.path.read_bytes() == before
    assert set(store.path.parent.iterdir()) == files
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_missing_empty_and_non_sqlite_never_initialized(tmp_path, activation):
    path = tmp_path / "missing.sqlite"
    for contents in (None, b"", b"not sqlite secret"):
        if contents is not None:
            path.write_bytes(contents)
        store = writer.UnattendedStateStore(path)
        with pytest.raises(UnattendedStateError):
            _verify(store, activation)
        if contents is None:
            assert not path.exists()
        else:
            with pytest.raises(UnattendedStateError):
                store.admit(activation)
            assert path.read_bytes() == contents


def test_busy_store_rejects_once_without_retry(store, activation, monkeypatch):
    current = store.admit(activation)
    real = sqlite3.connect
    calls = []
    with real(store.path) as locked:
        locked.execute("BEGIN IMMEDIATE")

        def connect(database, **kwargs):
            calls.append((database, kwargs))
            return real(database, **kwargs)

        monkeypatch.setattr(writer.sqlite3, "connect", connect)
        with pytest.raises(UnattendedStateError, match="without retry"):
            store.transition(current, state=State.PREPARE_STARTED, at=AT)
        assert len(calls) == 1 and calls[0][1]["timeout"] == 0
    assert store.admit(activation) == current


def test_one_cas_update_exact_predicate_and_timestamp(store, activation, monkeypatch):
    current = store.admit(activation)
    real = sqlite3.connect
    statements = []

    class Recording(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            statements.append((sql, parameters))
            return super().execute(sql, parameters)

    monkeypatch.setattr(
        writer.sqlite3,
        "connect",
        lambda database, **kwargs: real(database, factory=Recording, **kwargs),
    )
    result = store.transition(
        current, state=State.PREPARE_STARTED, at=AT + timedelta(seconds=7)
    )
    updates = [
        (sql, parameters) for sql, parameters in statements if sql.startswith("UPDATE")
    ]
    assert len(updates) == 1
    sql, parameters = updates[0]
    assert "activation_id=? AND wake_id=? AND wake_json=? AND revision=?" in sql
    assert parameters == (
        result.wake.to_json(),
        1,
        str(activation.activation_id),
        str(current.wake.wake_id),
        current.wake.to_json(),
        0,
    )
    assert result.wake.updated_at == AT + timedelta(seconds=7)


def test_paper_path_is_inert_and_same_path_rejected_before_sqlite(
    tmp_path, activation, monkeypatch
):
    paper_path = tmp_path / "inert-paper.sqlite"
    paper_path.write_bytes(b"paper secret sentinel")
    activation = replace(activation, store_path=str(paper_path))
    store = writer.UnattendedStateStore(tmp_path / "state.sqlite")
    store.admit(activation)
    assert _verify(store, activation).state == State.READY
    assert paper_path.read_bytes() == b"paper secret sentinel"
    bad = writer.UnattendedStateStore(paper_path)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: pytest.fail("paper opened"))
    with pytest.raises(UnattendedStateError, match="separate"):
        bad.admit(activation)
    with pytest.raises(UnattendedStateError, match="separate"):
        _verify(bad, activation)


@pytest.mark.parametrize(
    "module,allowed",
    [
        (
            verifier,
            {
                "__future__",
                "hashlib",
                "json",
                "sqlite3",
                "contextlib",
                "dataclasses",
                "pathlib",
                "uuid",
                "trading_bot.review_paper.unattended_activation",
                "trading_bot.review_paper.unattended_state_schema",
            },
        ),
        (
            writer,
            {
                "__future__",
                "sqlite3",
                "contextlib",
                "datetime",
                "pathlib",
                "trading_bot.review_paper.unattended_activation",
                "trading_bot.review_paper.unattended_state_schema",
                "trading_bot.review_paper.unattended_state_verifier",
            },
        ),
    ],
)
def test_closed_import_and_call_surface_no_provider_paper_scheduler(module, allowed):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8-sig"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported == allowed
    forbidden = {
        "open",
        "eval",
        "exec",
        "getenv",
        "environ",
        "now",
        "utcnow",
        "time",
        "sleep",
        "uuid4",
        "subprocess",
        "Popen",
        "retry",
        "poll",
        "repair",
        "migrate",
        "risk_manager",
        "provider",
        "scheduler",
        "store",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            assert name not in forbidden
    if module is verifier:
        assert not any(
            isinstance(node, ast.Name)
            and node.id in {"UnattendedStateStore", "transition_review_paper_wake"}
            for node in ast.walk(tree)
        )
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        assert not any(
            text.startswith(
                ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ")
            )
            for text in literals
        )


@pytest.mark.parametrize("failure", ["cas_zero", "post_update"])
def test_failed_cas_or_post_update_validation_rolls_back(
    store, activation, monkeypatch, failure
):
    current = store.admit(activation)
    before = store.snapshot()
    if failure == "cas_zero":
        real = sqlite3.connect

        class NoUpdate(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                if sql.startswith("UPDATE"):
                    return super().execute(sql + " AND 0", parameters)
                return super().execute(sql, parameters)

        monkeypatch.setattr(
            writer.sqlite3,
            "connect",
            lambda database, **kwargs: real(database, factory=NoUpdate, **kwargs),
        )
    else:
        real_read = writer.read_state_connection
        calls = []

        def fail_after_update(connection):
            calls.append(1)
            if len(calls) == 2:
                raise UnattendedStateError("injected validation failure")
            return real_read(connection)

        monkeypatch.setattr(writer, "read_state_connection", fail_after_update)
    with pytest.raises(UnattendedStateError):
        store.transition(current, state=State.PREPARE_STARTED, at=AT)
    assert store.snapshot() == before


@pytest.mark.parametrize(
    "at", [AT - timedelta(seconds=1), datetime(2026, 10, 5), "now"]
)
def test_invalid_caller_timestamp_never_commits(store, activation, at):
    current = store.admit(activation)
    before = store.snapshot()
    with pytest.raises((ValueError, TypeError)):
        store.transition(current, state=State.PREPARE_STARTED, at=at)
    assert store.snapshot() == before


def test_corrupt_unselected_activation_invalidates_complete_store(store, activation):
    store.admit(activation)
    other = replace(activation, deployment_identity="d" * 64)
    store.admit(other)
    _sql(
        store,
        "UPDATE activations SET activation_json='{}' WHERE activation_id=?",
        (str(other.activation_id),),
    )
    with pytest.raises(UnattendedStateError):
        _verify(store, activation)


@pytest.mark.parametrize("revision", [-1, 9223372036854775808.0])
def test_corrupt_revision_bounds_rejected_without_repair(store, activation, revision):
    store.admit(activation)
    with sqlite3.connect(store.path) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute("UPDATE wakes SET revision=?", (revision,))
    before = store.path.read_bytes()
    with pytest.raises(UnattendedStateError):
        _verify(store, activation)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("path", ["relative.sqlite", Path("relative.sqlite"), None])
def test_explicit_absolute_database_transport_required(path):
    with pytest.raises(UnattendedStateError):
        writer.UnattendedStateStore(path)
    with pytest.raises(UnattendedStateError):
        verifier.snapshot_unattended_state(path)


@pytest.mark.parametrize("bad_activation", [None, {}, "activation"])
def test_invalid_activation_inputs_reject_before_open(
    store, activation, bad_activation
):
    with pytest.raises(UnattendedStateError):
        store.admit(bad_activation)
    with pytest.raises(UnattendedStateError):
        verifier.verify_unattended_state(
            store.path,
            expected_activation=bad_activation,
            expected_wake_id=ReviewPaperWake(
                activation=activation, updated_at=AT
            ).wake_id,
        )
    assert not store.path.exists()


@pytest.mark.parametrize("value", [True, -1, "0", 1.5, MAX_REVISION + 1])
def test_invalid_verifier_expected_revision_rejected(store, activation, value):
    current = store.admit(activation)
    with pytest.raises(UnattendedStateError):
        verifier.verify_unattended_state(
            store.path,
            expected_activation=activation,
            expected_wake_id=current.wake.wake_id,
            expected_revision=value,
        )


def test_invalid_verifier_expected_wake_types_rejected(store, activation):
    current = store.admit(activation)
    with pytest.raises(UnattendedStateError):
        verifier.verify_unattended_state(
            store.path,
            expected_activation=activation,
            expected_wake_id=str(current.wake.wake_id),
        )
    with pytest.raises(UnattendedStateError):
        verifier.verify_unattended_state(
            store.path,
            expected_activation=activation,
            expected_wake_id=current.wake.wake_id,
            expected_wake="wake",
        )


@pytest.mark.parametrize("table", ["activations", "wakes"])
def test_weakened_duplicate_row_schema_rejected(store, activation, table):
    store.admit(activation)
    with sqlite3.connect(store.path) as connection:
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
        connection.execute(f"DROP TABLE {table}")
        columns = (
            "activation_id TEXT, activation_json TEXT"
            if table == "activations"
            else "activation_id TEXT, wake_id TEXT, wake_json TEXT, revision INTEGER"
        )
        connection.execute(f"CREATE TABLE {table} ({columns})")
        placeholders = ",".join("?" for _ in rows[0])
        connection.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows * 2)
    before = store.path.read_bytes()
    with pytest.raises(UnattendedStateError):
        _verify(store, activation)
    assert store.path.read_bytes() == before
