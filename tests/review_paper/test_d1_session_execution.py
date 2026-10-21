"""D1R8 fake-only source gate; no real host, credentials, provider or runtime."""

from __future__ import annotations

import ast
import copy
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.review_paper.test_armed_production_paper_session import AlpacaTransport
from tests.review_paper.test_risk_price_acquisition import _quote

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.review_paper import d1_session_authorization as q
from trading_bot.review_paper import d1_session_execution as c
from trading_bot.review_paper import d1_session_execution_host as host
from trading_bot.review_paper import d1_session_execution_store as s
from trading_bot.review_paper.armed_session_store import (
    ArmedSessionStore,
    recovery_reason_for,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.robinhood_mcp.account_resolution import RobinhoodAgenticAccountResolver
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 19, 14, tzinfo=UTC)
SOURCE = q.Source(s.BRANCH, "a" * 40, "b" * 40)
PRODUCER = q.Source(q.BRANCH, s.PRODUCER_HEAD, s.PRODUCER_TREE)


class FakeRobinhood:
    def __init__(self, fake):
        self.fake = fake
        self.calls = []
        self.pages = 1
        self.order = False
        self.wrong_echo = False
        self.stale = False
        self.price = "100"

    def call(self, name):
        self.calls.append(name)
        self.fake.hit(name)

    def quote(self):
        at = self.fake.now - timedelta(seconds=61) if self.stale else self.fake.now
        return _quote(
            "SPY",
            ask_price=self.price,
            bid_price=self.price,
            last_trade_price=self.price,
            venue_ask_time=at.isoformat(),
            venue_bid_time=at.isoformat(),
            venue_last_trade_time=at.isoformat(),
        )

    def get_equity_quotes(self, arguments):
        self.call("quote")
        assert arguments == {"symbols": ["SPY"]}
        return {"data": {"results": [{"quote": self.quote(), "close": None}]}}

    def accounts(self):
        self.call("account")
        return {
            "data": {
                "accounts": [
                    {"account_number": "FAKE-SECRET-ACCOUNT", "agentic_allowed": True}
                ]
            }
        }

    def get_equity_orders(self, arguments):
        self.call("orders")
        assert arguments["placed_agent"] == "agentic"
        assert arguments["symbol"] == "SPY"
        cursor = int(arguments.get("cursor", "0"))
        if self.order:
            raise ValueError("FAKE-SECRET-order-window")
        return {
            "data": {
                "orders": [],
                "next": str(cursor + 1) if cursor + 1 < self.pages else None,
            }
        }

    def review_equity_order(self, arguments):
        self.call("review")
        assert arguments["quantity"] == "1"
        return {
            "data": {
                "market_data_disclosure": "FAKE-SECRET-provider-body",
                "order_checks": {},
                "quantity": "2" if self.wrong_echo else "1",
                "quote_data": self.quote(),
                "side": "buy",
                "symbol": "SPY",
                "type": "market",
            }
        }


class Fake:
    def __init__(self, parent):
        self.parent = parent / "qualification"
        self.parent.mkdir()
        runtime = parent / "runtime"
        runtime.mkdir()
        self.paper_path = runtime / "paper.sqlite"
        self.session_path = runtime / "armed-sessions.sqlite"
        ReviewPaperStore(self.paper_path, starting_cash=Decimal("10000"))
        ArmedSessionStore(self.session_path).initialize()
        self.now = NOW
        self.source = SOURCE
        self.roots = (parent / "repository",)
        self.events = []
        self.guard_count = 0
        self.guard_fault = 0
        self.fault = None
        self.fail_n = 1
        self.secret_targets = []
        self.raw = AlpacaTransport()
        self.rh = FakeRobinhood(self)
        self.publish()

    def publish(self, *, plan=None, transform=None):
        plan = plan or q.Plan(PRODUCER, self.source, NOW - timedelta(minutes=1))
        rows = [q.record(plan, e) for e in q.EVENTS]
        if transform:
            transform(rows)
        payload = b"".join(q.canonical(r) + b"\n" for r in rows)
        self.predecessor = self.parent / plan.name
        self.predecessor.write_bytes(payload)
        self.proof = c.ReviewedProof(
            self.source, len(payload), hashlib.sha256(payload).hexdigest(), True
        )

    def hit(self, event):
        self.events.append(event)
        if event == self.fault and self.events.count(event) == self.fail_n:
            raise RuntimeError("FAKE-SECRET-raw-error bearer abcdef")

    def clock(self):
        return self.now

    def admit_source(self, source):
        self.guard_count += 1
        if self.guard_count == self.guard_fault:
            raise ValueError("fake source/tracking/live/import drift")
        assert source == self.source
        return self.roots

    def admit_runtime(self):
        self.hit("runtime")

    def write_readiness(self):
        self.hit("readiness")

    def read_credential(self, target):
        self.secret_targets.append(target)
        self.hit("credential")
        return bytearray(b"FAKE-SECRET-credential")

    def alpaca_transport(self):
        return self.raw

    def robinhood(self, records):
        assert len(records) == 2
        return RobinhoodReviewReadAdapter(self.rh), RobinhoodAgenticAccountResolver(
            self.rh.accounts
        )

    @property
    def output(self):
        return self.parent / s.reservation_name("2026-10-19")

    def run(self, interlock=c.INTERLOCK):
        return c.run_session(self, self.proof, interlock)

    def rows(self, complete=True):
        return s.parse_journal(self.output.read_bytes(), complete=complete)


@pytest.fixture
def fake(tmp_path):
    return Fake(tmp_path)


def cache_disposable_reads(monkeypatch):
    """Isolate non-filesystem matrices from repeated native open overhead."""
    original = q.read_evidence
    cache = {}

    def read(path, maximum, identity=None):
        info = path.stat()
        key = (
            path,
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_mode,
            info.st_nlink,
        )
        if info.st_size > maximum or (
            identity is not None and identity != (info.st_dev, info.st_ino)
        ):
            raise ValueError("fake stable read rejected")
        if key not in cache:
            cache[key] = original(path, maximum, identity)
        return cache[key]

    monkeypatch.setattr(q, "read_evidence", read)


def test_acknowledged_execution_uses_real_pure_components_and_fakes(fake):
    assert fake.run() == "PAPER_EXECUTED"
    rows = fake.rows()
    assert tuple(r["event"] for r in rows if r["action"] is None) == (
        *s.STATES,
        "FINAL",
    )
    counts = rows[-1]["effects"]
    assert counts["alpaca_history_requests"] == 4
    assert counts["credential_reads"] == 4
    assert counts["order_history_attempts"] == 2
    assert counts["paper_fill_mutations"] == 1
    assert (
        len(
            ReviewPaperStore(
                fake.paper_path, starting_cash=Decimal("10000"), read_only=True
            ).history()
        )
        == 1
    )
    assert fake.secret_targets == [
        c.API_KEY_TARGET,
        c.API_SECRET_TARGET,
        c.TOKEN_TARGET,
        c.CLIENT_TARGET,
    ]
    assert fake.rh.calls == ["quote", "account", "orders", "review", "orders"]
    assert b"FAKE-SECRET" not in fake.output.read_bytes()
    assert b"raw-error" not in fake.output.read_bytes()
    fence, _ = ArmedSessionStore(fake.session_path).read(
        "armed-paper-session/v1:SPY:2026-10-19"
    )
    with pytest.raises(ValueError):
        recovery_reason_for(fence)


def test_no_signal_never_reads_robinhood_or_prepares(fake):
    fake.raw.closes = (10, 10, 10, 10)
    assert fake.run() == "NO_SIGNAL"
    counts = fake.rows()[-1]["effects"]
    assert fake.secret_targets == [c.API_KEY_TARGET, c.API_SECRET_TARGET]
    assert not fake.rh.calls
    for key in (
        "robinhood_credential_reads",
        "prepare_attempts",
        "execute_attempts",
        "paper_fill_mutations",
    ):
        assert counts[key] == 0


def test_risk_rejection_is_safe_terminal_without_execution(fake):
    fake.rh.price = "1000000000000"
    assert fake.run() == "RISK_REJECTED"
    assert fake.rh.calls == ["quote"]
    assert fake.rows()[-1]["effects"]["paper_fill_mutations"] == 0


@pytest.mark.parametrize(
    "literal",
    [
        None,
        "",
        q.INTERLOCK,
        "AUTHORIZE_ARCH134_D1_ONE_SYNTHETIC_PAPER_SESSION",
        "AUTHORIZE_ARCH134_D1R2_ONE_PRE_EFFECT_HISTORY_RECOVERY",
    ],
)
def test_historical_interlocks_rejected_before_admission(fake, literal):
    with pytest.raises(ValueError):
        fake.run(literal)
    assert fake.guard_count == 0 and not fake.output.exists()


@pytest.mark.parametrize("proof", [None, {}, True, SimpleNamespace(source=SOURCE)])
def test_direct_controller_bypass_missing_proof(fake, proof):
    with pytest.raises(ValueError):
        c.run_session(fake, proof, c.INTERLOCK)
    assert not fake.events and not fake.output.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("publication_confirmed", False),
        ("publication_confirmed", 1),
        ("d1r7_bytes", True),
        ("d1r7_bytes", 0),
        ("d1r7_sha256", "bad"),
        ("source", q.Source(q.BRANCH, "a" * 40, "b" * 40)),
    ],
)
def test_proof_is_closed_review_assertions(fake, field, value):
    with pytest.raises(ValueError):
        replace(fake.proof, **{field: value})


@pytest.mark.parametrize("field", ["head", "tree"])
def test_wrong_successor_source(fake, field):
    fake.proof = replace(fake.proof, source=replace(SOURCE, **{field: "c" * 40}))
    fake.source = fake.proof.source
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "policy",
        "contract",
        "producer",
        "target",
        "budget",
        "effect",
        "authority",
        "terminal",
        "unknown",
        "missing",
        "boolean",
        "floating",
    ],
)
def test_bad_prerequisite_rejected_before_consumption(fake, mutation):
    def transform(rows):
        for row in rows:
            if mutation == "policy":
                row["facts"]["d1_policy"]["opening_buffer_seconds"] = 0
            if mutation == "contract":
                row["facts"]["strategy_contract"]["symbol"] = "QQQ"
            if mutation == "producer":
                row["facts"]["source"]["head"] = "e" * 40
            if mutation == "target":
                row["facts"]["target_session"] = "2026-10-20"
            if mutation == "budget":
                row["budgets"]["credential_reads"] = 1
            if mutation == "effect":
                row["effects"]["credential_reads"] = 1
            if mutation == "authority":
                row["authority"]["execute_authorized"] = True
            if mutation == "unknown":
                row["surprise"] = "secret"
            if mutation == "missing":
                row.pop("effects")
            if mutation == "boolean":
                row["effects"]["credential_reads"] = False
            if mutation == "floating":
                row["effects"]["credential_reads"] = 0.0
        if mutation == "terminal":
            rows[-1]["classification"] = "PASS"

    fake.publish(transform=transform)
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists() and not fake.secret_targets


@pytest.mark.parametrize(
    "corruption", ["duplicate", "crlf", "truncated", "trailing", "bom", "whitespace"]
)
def test_noncanonical_prerequisite(fake, corruption):
    payload = fake.predecessor.read_bytes()
    if corruption == "duplicate":
        payload = payload.replace(b'{"authority":', b'{"schema":"x","authority":', 1)
    if corruption == "crlf":
        payload = payload.replace(b"\n", b"\r\n")
    if corruption == "truncated":
        payload = payload[:-5]
    if corruption == "trailing":
        payload += b"{}\n"
    if corruption == "bom":
        payload = b"\xef\xbb\xbf" + payload
    if corruption == "whitespace":
        payload = b" " + payload
    fake.predecessor.write_bytes(payload)
    with pytest.raises((ValueError, FileNotFoundError)):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize("kind", ["hash", "size", "basename", "ambiguous"])
def test_reviewed_evidence_proof_required(fake, kind):
    if kind == "hash":
        fake.proof = replace(fake.proof, d1r7_sha256="f" * 64)
    if kind == "size":
        fake.proof = replace(fake.proof, d1r7_bytes=fake.proof.d1r7_bytes + 1)
    if kind == "basename":
        fake.predecessor.rename(fake.predecessor.with_name("other.jsonl"))
    if kind == "ambiguous":
        fake.proof = None
    with pytest.raises((ValueError, FileNotFoundError)):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize(
    "at",
    [
        NOW.replace(hour=13),
        NOW.replace(hour=19, minute=55),
        NOW + timedelta(days=1),
        NOW - timedelta(minutes=2),
    ],
)
def test_unadmitted_or_expired_session_precedes_reservation(fake, at):
    fake.now = at
    with pytest.raises((ValueError, FileNotFoundError)):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize(
    "event,n",
    [
        ("readiness", 1),
        ("credential", 1),
        ("credential", 2),
        ("credential", 3),
        ("credential", 4),
        ("quote", 1),
        ("account", 1),
        ("orders", 1),
        ("orders", 2),
        ("review", 1),
    ],
)
def test_first_effect_failure_stops_consumed_without_fallback(fake, event, n):
    fake.fault, fake.fail_n = event, n
    assert fake.run() == "INDETERMINATE"
    assert fake.events.count(event) == n
    assert fake.rows()[-1]["classification"] == "INDETERMINATE"
    with pytest.raises(ValueError):
        fake.run()
    assert b"FAKE-SECRET" not in fake.output.read_bytes()


@pytest.mark.parametrize(
    "fault",
    ["transport", "exception", "missing", "duplicate", "wrong_symbol", "pagination"],
)
def test_alpaca_failure_stops_at_first_of_four(fake, fault):
    fake.raw.fault = fault
    assert fake.run() in {"BLOCKED", "INDETERMINATE"}
    assert len(fake.raw.calls) == 1 and not fake.rh.calls


@pytest.mark.parametrize("kind", ["stale", "echo", "real_orders"])
def test_quote_review_and_order_window_revalidation(fake, kind):
    if kind == "stale":
        fake.rh.stale = True
    if kind == "echo":
        fake.rh.wrong_echo = True
    if kind == "real_orders":
        fake.rh.order = True
    assert fake.run() in {"BLOCKED", "INDETERMINATE"}
    assert fake.rows()[-1]["effects"]["paper_fill_mutations"] == 0


def test_order_history_limit_stops_without_101st_page(fake):
    fake.rh.pages = 101
    assert fake.run() == "BLOCKED"
    assert fake.rh.calls.count("orders") == 100
    assert "review" not in fake.rh.calls
    assert s.BUDGETS["order_history_attempts"] == 202


def test_maximum_successful_order_history_is_within_one_megabyte(fake, monkeypatch):
    # Pagination/counter sizing is independent of ancestor-link admission,
    # which has its own native path tests and public-reader regressions.
    monkeypatch.setattr(q, "checked_path", lambda _: None)
    monkeypatch.setattr(s.os, "fsync", lambda _: None)
    cache_disposable_reads(monkeypatch)
    fake.rh.pages = 100
    assert fake.run() == "PAPER_EXECUTED"
    assert fake.rows()[-1]["effects"]["order_history_attempts"] == 200
    assert fake.output.stat().st_size <= s.MAX_BYTES


def test_duplicate_rebuilt_and_restarted_attempts_collide(fake):
    fake.raw.closes = (10, 10, 10, 10)
    assert fake.run() == "NO_SIGNAL"
    original = fake.output.read_bytes()
    fake.source = replace(SOURCE, head="e" * 40, tree="f" * 40)
    fake.publish()
    with pytest.raises(ValueError):
        fake.run()
    assert fake.output.read_bytes() == original
    assert s.reservation_name("2026-10-19") == fake.output.name


def test_concurrent_exclusive_reservation_sacrifices_availability(fake):
    facts = dict(
        prerequisite=q.parse_authorization(fake.predecessor.read_bytes())[0]["facts"],
        d1r7_bytes=fake.proof.d1r7_bytes,
        d1r7_sha256=fake.proof.d1r7_sha256,
        publication_confirmed=True,
    )

    def reserve():
        try:
            journal = s.Journal(fake.parent, facts)
            journal.close()
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: reserve(), range(2))) == 1
    with pytest.raises(ValueError):
        fake.run()


@pytest.mark.parametrize(
    "sidecar", ["paper.sqlite-wal", "paper.sqlite-shm", "paper.sqlite-journal", "other"]
)
def test_runtime_sidecar_rejected_without_reservation(fake, sidecar):
    (fake.paper_path.parent / sidecar).write_bytes(b"fake")
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


def test_legacy_collision_precedes_reservation(fake):
    contract = c.ProductionStrategyContract.from_json(
        q.canonical(q.Plan(PRODUCER, SOURCE, NOW).facts["strategy_contract"]).decode()
    )
    ArmedSessionStore(fake.session_path).reserve(
        "armed-paper-session/v1:SPY:2026-10-19", c.compatibility_evidence(contract)
    )
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


def test_cli_has_no_semantic_or_destination_selectors():
    parser = host.build_parser()
    options = {o for action in parser._actions for o in action.option_strings}
    assert options == {
        "-h",
        "--help",
        "--accepted-head",
        "--accepted-tree",
        "--reviewed-d1r7-bytes",
        "--reviewed-d1r7-sha256",
        "--publication-confirmed",
    }
    assert parser.allow_abbrev is False
    with pytest.raises(ValueError):
        parser.parse_args(["--accepted-h", "a" * 40])


def test_host_requires_real_interactive_authorization(monkeypatch):
    monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    assert (
        host.main(
            [
                "--accepted-head",
                "a" * 40,
                "--accepted-tree",
                "b" * 40,
                "--reviewed-d1r7-bytes",
                "1",
                "--reviewed-d1r7-sha256",
                "c" * 64,
                "--publication-confirmed",
                "YES",
            ]
        )
        == 2
    )


def test_reachable_source_has_no_historical_controller_or_refresh_capability():
    for relative in (
        "src/trading_bot/review_paper/d1_session_execution.py",
        "src/trading_bot/review_paper/d1_session_execution_host.py",
    ):
        tree = ast.parse((ROOT / relative).read_text())
        calls = {
            n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))
        }
        assert not calls & {
            "run_armed_production_paper_session",
            "execute_production_strategy_paper_cycle",
            "execute_review_paper_supervised_cycle",
            "run_robinhood_paper_operator",
            "create_windows_robinhood_oauth_factory",
            "OAuthClientProvider",
            "write_generic",
            "CredWriteW",
            "CredDeleteW",
            "sleep",
            "place_order",
        }
    producer = (
        ROOT / "src/trading_bot/review_paper/d1_session_authorization_host.py"
    ).read_text()
    assert "d1_session_execution" not in producer


def test_each_guard_rejects_source_drift_before_next_effect(tmp_path, monkeypatch):
    # This matrix isolates source admission. Disk corruption/identity and native
    # durability have separate tests, so cache unchanged disposable ledger reads.
    for name in ("history", "reconstruct_ledger"):
        original = getattr(ReviewPaperStore, name)
        cache = {}

        def cached(self, original=original, cache=cache):
            key = (self.path, self.path.stat().st_mtime_ns)
            if key not in cache:
                cache[key] = original(self)
            return cache[key]

        monkeypatch.setattr(ReviewPaperStore, name, cached)
    monkeypatch.setattr(s.os, "fsync", lambda _: None)
    monkeypatch.setattr(q, "checked_path", lambda _: None)
    cache_disposable_reads(monkeypatch)
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    good = Fake(baseline)
    assert good.run() == "PAPER_EXECUTED"
    for ordinal in range(1, good.guard_count + 1):
        root = tmp_path / f"guard-{ordinal}"
        root.mkdir()
        runtime = Fake(root)
        runtime.guard_fault = ordinal
        try:
            result = runtime.run()
        except ValueError:
            assert not runtime.output.exists()
        else:
            assert result in {"BLOCKED", "INDETERMINATE"}
        assert runtime.guard_count == ordinal


@pytest.mark.parametrize("event", tuple(dict.fromkeys(s.STATES)))
@pytest.mark.parametrize("after", [False, True])
def test_interruptions_at_every_state_are_consumed(fake, monkeypatch, event, after):
    # The native-I/O matrix owns fsync failure semantics; this matrix isolates
    # interruption ordering while retaining write/flush/identity/readback.
    monkeypatch.setattr(s.os, "fsync", lambda _: None)
    monkeypatch.setattr(q, "checked_path", lambda _: None)
    cache_disposable_reads(monkeypatch)
    original = s.Journal.append
    fired = False

    def append(self, state, at, **kwargs):
        nonlocal fired
        if state == event and kwargs.get("action") is None and not fired:
            fired = True
            if after:
                original(self, state, at, **kwargs)
            raise OSError("FAKE-SECRET-crash")
        return original(self, state, at, **kwargs)

    monkeypatch.setattr(s.Journal, "append", append)
    assert fake.run() in {"BLOCKED", "INDETERMINATE"}
    assert fired and fake.output.exists()
    with pytest.raises(ValueError):
        fake.run()


@pytest.mark.parametrize(
    "phase",
    ["create_before", "create_after", "write", "flush", "fsync", "close", "readback"],
)
@pytest.mark.parametrize("after", [False, True])
def test_native_journal_io_failures_never_reclaim(fake, monkeypatch, phase, after):
    original_open, original_fdopen = s.os.open, s.os.fdopen
    original_fsync, original_read = s.os.fsync, q.read_evidence
    fired = False

    def fail():
        nonlocal fired
        fired = True
        raise OSError("FAKE-SECRET-io")

    def opened(path, flags, *args):
        if Path(path) == fake.output and phase == "create_before" and not fired:
            fail()
        fd = original_open(path, flags, *args)
        if Path(path) == fake.output and phase == "create_after" and not fired:
            os.close(fd)
            fail()
        return fd

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def fileno(self):
            return self.stream.fileno()

        def perform(self, name, *args):
            target = name == phase and not fired
            if target and not after:
                fail()
            result = getattr(self.stream, name)(*args)
            if target:
                fail()
            return result

        def write(self, value):
            return self.perform("write", value)

        def flush(self):
            return self.perform("flush")

        def close(self):
            # Close the owned descriptor even when simulating pre-close failure.
            target = phase == "close" and not fired
            self.stream.close()
            if target:
                fail()

    def fdopen(fd, mode):
        stream = original_fdopen(fd, mode)
        return Stream(stream) if mode == "wb" else stream

    def fsync(fd):
        if phase == "fsync" and not fired:
            if after:
                original_fsync(fd)
            fail()
        return original_fsync(fd)

    def read(path, *args):
        if path == fake.output and phase == "readback" and not fired:
            if after:
                original_read(path, *args)
            fail()
        return original_read(path, *args)

    monkeypatch.setattr(s.os, "open", opened)
    monkeypatch.setattr(s.os, "fdopen", fdopen)
    monkeypatch.setattr(s.os, "fsync", fsync)
    monkeypatch.setattr(q, "read_evidence", read)
    try:
        result = fake.run()
        assert result == "INDETERMINATE"
    except OSError:
        pass
    assert fired
    if phase != "close":
        assert not fake.secret_targets
    if phase != "create_before":
        assert fake.output.exists()
        with pytest.raises(ValueError):
            fake.run()


def test_compatibility_reservation_failure_is_uncertain(fake, monkeypatch):
    def reserve(*args):
        raise OSError("FAKE-SECRET-reservation")

    monkeypatch.setattr(ArmedSessionStore, "reserve", reserve)
    assert fake.run() == "INDETERMINATE"
    assert not fake.secret_targets
    assert fake.rows()[-1]["effects"]["compatibility_reservations"] == 1


@pytest.mark.parametrize(
    "kind",
    ["expiry", "regression", "prerequisite_mutation", "substitution", "paper_drift"],
)
def test_drift_during_slow_quote_is_rejected_before_execute(fake, kind):
    original = fake.rh.get_equity_quotes

    def quote(arguments):
        result = original(arguments)
        if kind == "expiry":
            fake.now = NOW.replace(hour=19, minute=55)
        if kind == "regression":
            fake.now -= timedelta(seconds=1)
        if kind == "prerequisite_mutation":
            fake.predecessor.write_bytes(b"changed")
        if kind == "substitution":
            saved = fake.predecessor.with_suffix(".saved")
            fake.predecessor.rename(saved)
            fake.predecessor.write_bytes(saved.read_bytes())
        if kind == "paper_drift":
            fake.paper_path.rename(fake.paper_path.with_suffix(".saved"))
            ReviewPaperStore(fake.paper_path, starting_cash=Decimal("10000"))
        return result

    fake.rh.get_equity_quotes = quote
    assert fake.run() in {"BLOCKED", "INDETERMINATE"}
    assert "account" not in fake.rh.calls
    assert fake.rows()[-1]["effects"]["paper_fill_mutations"] == 0


def test_paper_acknowledgement_failure_never_retries(fake, monkeypatch):
    original = ReviewPaperStore.record_market_review

    def write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise OSError("FAKE-SECRET-ack")

    monkeypatch.setattr(ReviewPaperStore, "record_market_review", write)
    assert fake.run() == "INDETERMINATE"
    assert fake.rows()[-1]["effects"]["paper_fill_mutations"] == 1
    assert (
        len(
            ReviewPaperStore(
                fake.paper_path, starting_cash=Decimal("10000"), read_only=True
            ).history()
        )
        == 1
    )
    with pytest.raises(ValueError):
        fake.run()


@pytest.mark.parametrize("target", ["predecessor", "paper_path", "session_path"])
def test_hardlinked_authority_or_sqlite_paths_rejected(fake, target):
    path = getattr(fake, target)
    os.link(path, path.with_name(path.name + ".hardlink"))
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "duplicate",
        "missing",
        "bool",
        "float",
        "counter",
        "budget",
        "state",
        "pending",
        "terminal",
        "secret",
        "overlong",
        "authority",
    ],
)
def test_canonical_parser_rejects_forged_evidence(fake, mutation):
    fake.raw.closes = (10, 10, 10, 10)
    assert fake.run() == "NO_SIGNAL"
    rows = list(copy.deepcopy(fake.rows()))
    if mutation == "unknown":
        rows[0]["extra"] = "bad"
    if mutation == "missing":
        rows[0].pop("effects")
    if mutation == "bool":
        rows[-1]["effects"]["credential_reads"] = True
    if mutation == "float":
        rows[-1]["effects"]["credential_reads"] = 2.0
    if mutation == "counter":
        rows[-1]["effects"]["paper_fill_mutations"] = 1
    if mutation == "budget":
        rows[0]["budgets"]["broker_placements"] = 1
    if mutation == "state":
        rows[1]["event"] = "STRATEGY_STARTED"
    if mutation == "pending":
        rows.pop(-3)
    if mutation == "terminal":
        rows[-1]["classification"] = "PAPER_EXECUTED"
    if mutation == "secret":
        rows[-1]["counter"] = "FAKE-SECRET"
    if mutation == "overlong":
        rows[0]["binding_sha256"] = "x" * (s.MAX_BYTES + 1)
    if mutation == "authority":
        rows[0]["facts"]["publication_confirmed"] = 1
    payload = b"".join(q.canonical(r) + b"\n" for r in rows)
    if mutation == "duplicate":
        payload = payload.replace(b'{"action":', b'{"action":null,"action":', 1)
    with pytest.raises(ValueError):
        s.parse_journal(payload)


@pytest.mark.parametrize("family", ["alpaca", "robinhood"])
def test_exact_fixed_credential_targets_cannot_be_reacquired(monkeypatch, family):
    runtime = host.FixedRuntime()
    calls = []

    def read(target):
        calls.append(target)
        return bytearray(b"fake-secret")

    from trading_bot.arch133_verifier import credentials
    from trading_bot.review_paper import alpaca_windows_credentials

    monkeypatch.setattr(
        alpaca_windows_credentials, "read_fixed_current_product_credential", read
    )
    monkeypatch.setattr(
        credentials,
        "WindowsCredentialReader",
        lambda: SimpleNamespace(read_generic=read),
    )
    targets = (
        (c.API_KEY_TARGET, c.API_SECRET_TARGET)
        if family == "alpaca"
        else (c.TOKEN_TARGET, c.CLIENT_TARGET)
    )
    for target in targets:
        assert runtime.read_credential(target) == b"fake-secret"
        with pytest.raises(ValueError):
            runtime.read_credential(target)
    with pytest.raises(ValueError):
        runtime.read_credential("arbitrary")
    assert calls == list(targets)


def test_persisted_auth_has_single_yield_and_no_refresh_or_storage():
    httpx2 = pytest.importorskip("httpx2")
    pytest.importorskip("mcp.shared.auth")
    auth = host.persisted_auth(
        (
            bytearray(
                b'{"access_token":"FAKE-SECRET","token_type":"Bearer","expires_in":3600}'
            ),
            bytearray(b'{"client_id":"fake-client"}'),
        )
    )
    request = httpx2.Request("POST", "https://agent.robinhood.com/mcp/trading")
    flow = auth.auth_flow(request)
    assert next(flow).headers["Authorization"] == "Bearer FAKE-SECRET"
    with pytest.raises(StopIteration):
        flow.send(httpx2.Response(401))
    assert "FAKE-SECRET" not in repr(auth)
    bad = auth.auth_flow(httpx2.Request("POST", "https://evil.invalid/mcp/trading"))
    with pytest.raises(ValueError):
        next(bad)


def test_checkpoint_inventory_and_explicit_successor():
    name = "arch134-d1r8-d1-session-execution-consumer"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), s.BRANCH, "push")
        == name
    )
    assert runner.resolve_ci_certification_profile(name) == "robinhood"
    assert runner._arch134_d1r8_authority_check(ROOT) == ()
    inventory = certification.discover_inventory(ROOT)
    assert {
        p: len(certification.select_inventory(inventory, p))
        for p in certification.PROFILES
    } == {"full": 192, "robinhood": 103, "legacy": 222, "exhaustive": 414}
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 70
    assert len([p for p in inventory if p.startswith("tests/gui/")]) == 51


@pytest.mark.parametrize(
    "path",
    [
        "tests/runtime/checkpoint_runner/test_core.py",
        "tests/scripts/certification_runner/test_profiles.py",
    ],
)
def test_every_successor_layer_executes_once(monkeypatch, path):
    calls = []
    for name in (
        "_arch134_d1r6_test_pin",
        "_arch134_d1r7_test_pin",
        "_arch134_d1r8_test_pin",
        "_arch142_current_inventory_test_pin",
        "_arch142b_current_inventory_test_pin",
        "_arch143_current_inventory_test_pin",
        "_arch132_r3i_current_inventory_test_pin",
        "_arch144_current_inventory_test_pin",
        "_arch134_f1_current_inventory_test_pin",
        "_canonical_current_inventory_test_pin",
    ):
        original = getattr(runner, name)

        def traced(*args, name=name, original=original):
            calls.append(name)
            return original(*args)

        monkeypatch.setattr(runner, name, traced)
    pin = runner.ARCH134_D1R5_TEST_PIN_OVERRIDES[path]
    if path in runner.CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        pin = runner._arch134_d1r6_test_pin(path, pin)
    pin = runner._canonical_current_inventory_test_pin(path, pin)
    pin = runner._arch134_d1r7_test_pin(path, pin)
    if path in runner.ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        pin = runner._arch142_current_inventory_test_pin(path, pin)
    if path in runner.ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        pin = runner._arch142b_current_inventory_test_pin(path, pin)
    if path in runner.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        pin = runner._arch143_current_inventory_test_pin(path, pin)
    if path in runner.ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES:
        pin = runner._arch132_r3i_current_inventory_test_pin(path, pin)
    if path in runner.ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        pin = runner._arch144_current_inventory_test_pin(path, pin)
    else:
        pin = runner._arch134_f1_current_inventory_test_pin(path, pin)
    assert pin == runner._git_blob_sha1(ROOT / path)
    first = ["_arch134_d1r6_test_pin", "_canonical_current_inventory_test_pin"]
    if path not in runner.CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        first.reverse()
    assert calls == [
        *first,
        "_arch134_d1r7_test_pin",
        "_arch134_d1r8_test_pin",
        *(
            ["_arch142_current_inventory_test_pin"]
            if path in runner.ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
            else []
        ),
        *(
            ["_arch142b_current_inventory_test_pin"]
            if path in runner.ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
            else []
        ),
        *(
            ["_arch143_current_inventory_test_pin"]
            if path in runner.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
            else []
        ),
        *(
            ["_arch132_r3i_current_inventory_test_pin"]
            if path in runner.ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES
            else []
        ),
        *(
            ["_arch144_current_inventory_test_pin"]
            if path in runner.ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
            else []
        ),
        "_arch134_f1_current_inventory_test_pin",
    ]


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "source", "value", "predecessor"]
)
def test_final_overlay_is_closed_and_preserves_all_predecessors(monkeypatch, mutation):
    pins = dict(runner.ARCH134_D1R8_TEST_PIN_OVERRIDES)
    path = next(iter(pins))
    prior = runner.ARCH134_D1R8_PREDECESSOR_TEST_PINS[path]
    if mutation == "missing":
        pins.pop(path)
    if mutation == "extra":
        pins["tests/unreviewed.py"] = "a" * 40
    if mutation == "source":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    if mutation == "value":
        pins[path] = "a" * 40
    if mutation == "predecessor":
        prior = "f" * 40
    monkeypatch.setattr(runner, "ARCH134_D1R8_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch134_d1r8_test_pin(path, prior)


@pytest.mark.parametrize("producer", [False, True])
@pytest.mark.parametrize(
    "drift",
    [
        None,
        "root",
        "branch",
        "head",
        "tree",
        "dirty",
        "origin",
        "push_origin",
        "upstream",
        "tracking_head",
        "tracking_tree",
        "live",
        "registry",
        "mixed_file",
        "mixed_package",
    ],
)
def test_fixed_host_admits_local_tracking_live_and_unmixed_imports(
    tmp_path, monkeypatch, producer, drift
):
    predecessor = tmp_path / "producer"
    predecessor.mkdir()
    monkeypatch.setattr(host, "WORKTREE", ROOT)
    monkeypatch.setattr(host, "PRODUCER_WORKTREE", predecessor)
    registry = f"worktree {ROOT}\n\nworktree {predecessor}\n"
    keys = [
        "root",
        "branch",
        "head",
        "tree",
        "dirty",
        "origin",
        "push_origin",
        "upstream",
        "tracking_head",
        "tracking_tree",
        "live",
        "registry",
    ]

    def git(command, **kwargs):
        root = Path(command[2])
        own = root == ROOT
        source = SOURCE if own else PRODUCER
        values = {
            ("rev-parse", "--show-toplevel"): str(root),
            ("branch", "--show-current"): source.branch,
            ("rev-parse", "HEAD"): source.head,
            ("rev-parse", "HEAD^{tree}"): source.tree,
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
            ("remote", "get-url", "origin"): q.ORIGIN,
            ("remote", "get-url", "--push", "origin"): q.ORIGIN,
            ("rev-parse", "--symbolic-full-name", "@{upstream}"): "refs/remotes/origin/"
            + source.branch,
            ("rev-parse", "origin/" + source.branch): source.head,
            ("rev-parse", "origin/" + source.branch + "^{tree}"): source.tree,
            ("ls-remote", "origin", "refs/heads/" + source.branch): source.head
            + "\trefs/heads/"
            + source.branch,
            ("worktree", "list", "--porcelain"): registry,
        }
        if drift in keys and own != producer:
            values[list(values)[keys.index(drift)]] = "wrong"
        return SimpleNamespace(stdout=values[tuple(command[3:])])

    monkeypatch.setattr(host.subprocess, "run", git)
    module = SimpleNamespace(
        __file__=str(ROOT / "src/trading_bot/__init__.py"),
        __path__=[str(ROOT / "src/trading_bot")],
    )
    if drift == "mixed_file":
        module.__file__ = str(predecessor / "module.py")
    if drift == "mixed_package":
        module.__path__ = [str(predecessor)]
    monkeypatch.setattr(host, "sys", SimpleNamespace(modules={"trading_bot": module}))
    if drift:
        with pytest.raises(ValueError):
            host.admit_source(SOURCE)
    else:
        assert host.admit_source(SOURCE) == (ROOT, predecessor)


@pytest.mark.parametrize(
    "name",
    [
        "ARCH134_D1R7_SOURCE_PINS",
        "ARCH134_D1R7_TEST_PIN_OVERRIDES",
        "ARCH134_D1R7_PREDECESSOR_TEST_PINS",
        "ARCH134_D1R7_PREDECESSOR_DIGESTS",
    ],
)
def test_frozen_d1r7_dictionary_digests(name):
    assert (
        s.digest(getattr(runner, name)) == runner.ARCH134_D1R8_PREDECESSOR_DIGESTS[name]
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/trading_bot/review_paper/armed_session.py",
        "src/trading_bot/review_paper/armed_session_host.py",
        "src/trading_bot/review_paper/armed_session_store.py",
        "src/trading_bot/review_paper/d1_session_authorization.py",
        "src/trading_bot/review_paper/d1_session_authorization_host.py",
        "scripts/run_arch134_d1r7.py",
    ],
)
def test_historical_executables_retain_frozen_source_pins(path):
    pins = {
        **runner.ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES,
        **runner.ARCH134_D1R5_SOURCE_PINS,
        **runner.ARCH134_D1R6_SOURCE_PINS,
        **runner.ARCH134_D1R7_SOURCE_PINS,
    }
    assert runner._git_blob_sha1(ROOT / path) == pins[path]


@pytest.mark.parametrize("kind", ["link", "reparse"])
def test_link_and_reparse_metadata_rejected_before_reservation(fake, monkeypatch, kind):
    import stat

    original = Path.lstat

    def lstat(path):
        metadata = original(path)
        if path == fake.predecessor:
            return SimpleNamespace(
                st_dev=metadata.st_dev,
                st_ino=metadata.st_ino,
                st_mode=stat.S_IFLNK if kind == "link" else metadata.st_mode,
                st_file_attributes=0x400 if kind == "reparse" else 0,
            )
        return metadata

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


def test_wal_header_rejected_before_any_sqlite_or_runtime_admission(fake):
    payload = bytearray(fake.paper_path.read_bytes())
    payload[18:20] = b"\x02\x02"
    fake.paper_path.write_bytes(payload)
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.events and not fake.output.exists()


def test_mutable_credentials_are_cleared_even_when_acknowledgement_fails(
    fake, monkeypatch
):
    secret = bytearray(b"FAKE-SECRET")
    fake.read_credential = lambda _: secret
    original = s.Journal.append

    def append(self, event, at, **kwargs):
        if (
            kwargs.get("counter") == "alpaca_credential_reads"
            and kwargs.get("action") == "ACK"
        ):
            raise OSError("fake ACK failure")
        return original(self, event, at, **kwargs)

    monkeypatch.setattr(s.Journal, "append", append)
    assert fake.run() == "INDETERMINATE"
    assert secret == b"\x00" * len(secret)


@pytest.mark.parametrize(
    "record",
    [
        b'{"access_token":"x","token_type":"Bearer","expires_in":0}',
        b'{"access_token":"x","access_token":"y","token_type":"Bearer"}',
        b'{"access_token":"x","token_type":"Basic"}',
        b"{}",
    ],
)
def test_persisted_token_rejection_has_no_renewal_path(record):
    pytest.importorskip("httpx2")
    pytest.importorskip("mcp.shared.auth")
    with pytest.raises(ValueError):
        host.persisted_auth(
            (bytearray(record), bytearray(b'{"client_id":"fake-client"}'))
        )


def test_history_decision_preparation_and_fill_have_sanitized_hashes(fake):
    assert fake.run() == "PAPER_EXECUTED"
    rows = fake.rows()
    hashed = [r for r in rows if r["result_sha256"] is not None]
    assert {r["event"] for r in hashed} == s.HASHED_STATES
    assert all(len(r["result_sha256"]) == 64 for r in hashed)
    rows = list(copy.deepcopy(rows))
    next(r for r in rows if r["event"] == "HISTORY_READY")["result_sha256"] = None
    with pytest.raises(ValueError):
        s.parse_journal(b"".join(q.canonical(r) + b"\n" for r in rows))


def test_valid_nonempty_real_order_window_blocks_before_review(fake, monkeypatch):
    from tests.test_robinhood_paper_cycle import _real_order

    from trading_bot.robinhood_mcp.models import RobinhoodEquityOrdersPage

    monkeypatch.setattr(
        RobinhoodReviewReadAdapter,
        "agentic_equity_orders",
        lambda *args, **kwargs: RobinhoodEquityOrdersPage(
            orders=(_real_order(),), next_cursor=None
        ),
    )
    assert fake.run() == "BLOCKED"
    assert "review" not in fake.rh.calls
    assert fake.rows()[-1]["effects"]["paper_fill_mutations"] == 0


def test_existing_target_paper_fill_blocks_before_reservation(fake):
    from tests.review_paper.test_store import _intent, _review

    ReviewPaperStore(
        fake.paper_path, starting_cash=Decimal("10000")
    ).record_market_review(_intent(proposed_at=NOW), _review(quote_time=NOW))
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists() and not fake.secret_targets


def test_terminal_record_cannot_replace_reservation(fake):
    fake.raw.closes = (10, 10, 10, 10)
    assert fake.run() == "NO_SIGNAL"
    rows = list(copy.deepcopy(fake.rows()))
    row = rows[-1]
    row["facts"] = rows[0]["facts"]
    row["classification"] = "BLOCKED"
    row["effects"] = dict.fromkeys(s.BUDGETS, 0)
    with pytest.raises(ValueError):
        s.parse_journal(q.canonical(row) + b"\n")


@pytest.mark.parametrize(
    "option",
    [
        "--source-branch",
        "--target-date",
        "--strategy",
        "--provider",
        "--account",
        "--runtime-path",
        "--price",
        "--quantity",
        "--evidence",
        "--order-id",
    ],
)
def test_cli_semantic_injection_rejected_with_complete_proof_arguments(option):
    valid = [
        "--accepted-head",
        "a" * 40,
        "--accepted-tree",
        "b" * 40,
        "--reviewed-d1r7-bytes",
        "1",
        "--reviewed-d1r7-sha256",
        "c" * 64,
        "--publication-confirmed",
        "YES",
    ]
    with pytest.raises(ValueError):
        host.build_parser().parse_args([*valid, option, "injected"])
