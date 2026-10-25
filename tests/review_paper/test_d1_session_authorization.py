"""D1R7 source-only regression: fake clocks/Git and disposable external files."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.review_paper import d1_session_authorization as q
from trading_bot.review_paper import d1_session_authorization_host as host
from trading_bot.review_paper import pre_market_wake_overnight as arm
from trading_bot.review_paper import pre_market_wake_qualification as wake

ROOT = Path(__file__).resolve().parents[2]
SOURCE = q.Source(q.BRANCH, "a" * 40, "b" * 40)
INTENDED = q.Source(q.D1_BRANCH, "c" * 40, "d" * 40)
NOW = datetime(2026, 10, 19, 13, tzinfo=UTC)


def wake_payload():
    opened = datetime(2026, 10, 16, 13, 30, tzinfo=UTC)
    records = []
    for index, event in enumerate(
        (
            "QUALIFICATION_RESERVED",
            "SOURCE_ADMITTED",
            "WAITING_FOR_MARKET",
            "WAKE_OBSERVED",
            "SOURCE_READMITTED",
            "FINAL",
        )
    ):
        records.append(
            {
                "schema": wake.SCHEMA,
                "event": event,
                "source_head": q.D1R5.head,
                "source_tree": q.D1R5.tree,
                "target_session": q.QUALIFICATION_SESSION,
                "regular_opens_at": opened.isoformat(),
                "regular_closes_at": opened.replace(hour=20, minute=0).isoformat(),
                "admission_opens_at": (opened + timedelta(minutes=5)).isoformat(),
                "admission_closes_at": opened.replace(hour=19, minute=55).isoformat(),
                "start_observed_at": (opened - timedelta(minutes=10)).isoformat(),
                "wait_started_at": (opened - timedelta(minutes=10)).isoformat()
                if index >= 2
                else None,
                "wait_seconds": 900.0 if index >= 2 else None,
                "wake_observed_at": (opened + timedelta(minutes=5)).isoformat()
                if index >= 3
                else None,
                "source_readmitted": index >= 4,
                "classification": "PASS" if event == "FINAL" else None,
                **dict.fromkeys(wake.EFFECT_COUNTERS, 0),
            }
        )
    return wake.serialize_wake_journal(tuple(records))


def arm_payload():
    plan = arm.Plan(
        q.D1R6.head,
        q.D1R6.tree,
        datetime(2026, 10, 16, 3, tzinfo=UTC),
        arm.Principal(r"DESKTOP\Owner", "S-1-5-21-1-2-3-1001"),
    )
    return arm.serialize_arm(
        tuple(
            {
                "schema": arm.SCHEMA,
                "event": event,
                "facts": plan.facts,
                "effects": dict.fromkeys(arm.ZERO_EFFECTS, 0),
                "scheduler_task_create_calls": int(index >= 4),
                "classification": "ARMED" if event == "FINAL" else None,
            }
            for index, event in enumerate((*arm.EVENTS, "FINAL"))
        )
    )


class Fake:
    def __init__(self, parent):
        self.parent = parent
        self.now = NOW
        self.calls = []
        self.fail_at = 0
        self.roots = (parent.parent / "repository",)

    def admit(self, source):
        self.calls.append(source)
        if len(self.calls) == self.fail_at:
            raise ValueError("fake source drift")
        return self.roots

    def clock(self):
        return self.now

    def run(self, source=SOURCE, intended=INTENDED, interlock=q.INTERLOCK):
        return q.publish_prerequisite(self, source, intended, interlock)

    @property
    def output(self):
        return self.parent / q.Plan(SOURCE, INTENDED, NOW).name


@pytest.fixture
def fake(tmp_path, monkeypatch):
    # Synthetic lengths/hashes are test-only; production pins are tested separately.
    parent = tmp_path / "qualification"
    parent.mkdir()
    for name, payload in (("D1R5", wake_payload()), ("D1R6", arm_payload())):
        pin = getattr(q, name)
        monkeypatch.setattr(
            q,
            name,
            replace(pin, size=len(payload), sha256=hashlib.sha256(payload).hexdigest()),
        )
        (parent / pin.basename).write_bytes(payload)
    return Fake(parent)


def test_frozen_real_predecessor_pins():
    assert q.D1R5 == q.EvidencePin(
        "arch134-d1r5-2026-10-16-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343.jsonl",
        6714,
        "9967e978cbf5f97afd9453e24fcfc3cdee4e864b589751fda3051c833b6d32cf",
        "arch134-d1r5-pre-market-wake-qualification/v1",
        "7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343",
        "c826c2a71e6d907866ce3f80afce479d38ab7842",
    )
    assert q.D1R6 == q.EvidencePin(
        "arch134-d1r6-2026-10-16-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343-"
        "a36de3bfe81a6e1a94fb3deeec7e579145939f52-6cde732e02e92eb2b34281672cdb7744250355b1.jsonl",
        19321,
        "837825d8cb3042431276bf6b7bdee0580da40ee2ef6a761eace86976924275f2",
        "arch134-d1r6-overnight-wake-arming/v1",
        "a36de3bfe81a6e1a94fb3deeec7e579145939f52",
        "6cde732e02e92eb2b34281672cdb7744250355b1",
    )
    assert str(q.PARENT) == r"F:\AI\temp\qualification"
    assert q.QUALIFICATION_SESSION == "2026-10-16"


def test_ready_is_only_prerequisite(fake):
    assert fake.run() == q.READY
    records = q.parse_authorization(fake.output.read_bytes())
    assert tuple(r["event"] for r in records) == q.EVENTS
    assert fake.calls == [SOURCE, INTENDED, SOURCE, INTENDED]
    facts = records[-1]["facts"]
    assert facts["target_session"] == "2026-10-19"
    assert facts["qualification_session"] == "2026-10-16"
    assert facts["authorization_expires_at"] == "2026-10-19T19:55:00+00:00"
    assert facts["d1r6"]["historical_scheduler_create_calls"] == 1
    assert facts["d1r6"]["authority_kind"] == "ORDINARY_ARM"
    assert facts["d1r5"]["final"] == "PASS" and facts["d1r6"]["final"] == "ARMED"
    for r in records:
        assert r["authority"] == dict.fromkeys(q.AUTHORITY, False)
        for field in ("budgets", "effects"):
            assert set(r[field]) == set(q.COUNTERS)
            assert all(type(v) is int and v == 0 for v in r[field].values())
    strategy = q.ProductionStrategyContract.from_json(
        q.canonical(facts["strategy_contract"]).decode()
    )
    assert strategy.source_head == INTENDED.head
    assert strategy.target_session_date == date(2026, 10, 19)
    assert strategy.strategy_id == "MovingAverageCrossoverStrategy"
    assert strategy.strategy_version == "1.0.0" and str(strategy.symbol) == "SPY"
    assert facts["d1_policy"] == q.fixed_policy()


@pytest.mark.parametrize("pin_name", ["D1R5", "D1R6"])
@pytest.mark.parametrize(
    "damage", ["missing", "empty", "partial", "corrupt", "hash", "basename"]
)
def test_bad_predecessor_no_reservation(fake, pin_name, damage):
    pin = getattr(q, pin_name)
    path = fake.parent / pin.basename
    data = path.read_bytes()
    if damage == "missing":
        path.unlink()
    elif damage == "basename":
        path.rename(path.with_name("alternate.jsonl"))
    else:
        path.write_bytes(
            {
                "empty": b"",
                "partial": data[:-1],
                "corrupt": b"{",
                "hash": data.replace(b"2026", b"2027", 1),
            }[damage]
        )
    with pytest.raises((ValueError, OSError)):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize("pin_name", ["D1R5", "D1R6"])
@pytest.mark.parametrize(
    "damage", ["source", "session", "schema", "terminal", "sequence", "one_create"]
)
def test_semantic_predecessor_rejection_even_with_test_hash(
    fake, monkeypatch, pin_name, damage
):
    pin = getattr(q, pin_name)
    path = fake.parent / pin.basename
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    if damage == "source":
        for r in rows:
            (r if pin_name == "D1R5" else r["facts"])["source_head"] = "f" * 40
    elif damage == "session":
        for r in rows:
            (r if pin_name == "D1R5" else r["facts"])["target_session"] = "2026-10-15"
    elif damage == "schema":
        rows[-1]["schema"] = "other/v1"
    elif damage == "terminal":
        rows[-1]["classification"] = "INDETERMINATE"
    elif damage == "sequence":
        rows.pop(2)
    else:
        rows[-1][
            "scheduler_task_create_calls" if pin_name == "D1R6" else "scheduler_changes"
        ] = 0 if pin_name == "D1R6" else 1
    data = b"".join(q.canonical(r) + b"\n" for r in rows)
    path.write_bytes(data)
    monkeypatch.setattr(
        q,
        pin_name,
        replace(pin, size=len(data), sha256=hashlib.sha256(data).hexdigest()),
    )
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize(
    "clock,day,expiry",
    [
        ("2026-10-19T03:00:00+00:00", None, None),  # still Sunday in New York
        ("2026-10-19T04:00:00+00:00", "2026-10-19", 19),
        ("2026-10-19T19:54:59.999999+00:00", "2026-10-19", 19),
        ("2026-10-19T19:55:00+00:00", None, None),
        ("2026-11-02T14:00:00+00:00", "2026-11-02", 20),
        ("2026-11-27T17:54:59+00:00", "2026-11-27", 17),
        ("2026-11-27T17:55:00+00:00", None, None),
        ("2026-11-26T14:00:00+00:00", None, None),
        ("2029-01-02T14:00:00+00:00", None, None),
    ],
)
def test_current_published_session_only(clock, day, expiry):
    if day is None:
        with pytest.raises(ValueError):
            q.Plan(SOURCE, INTENDED, datetime.fromisoformat(clock))
    else:
        plan = q.Plan(SOURCE, INTENDED, datetime.fromisoformat(clock))
        assert plan.target.isoformat() == day and plan.expires_at.hour == expiry


@pytest.mark.parametrize(
    "bad", ["AUTHORIZE_ARCH134_D1_ONE_SYNTHETIC_PAPER_SESSION", "", None, True]
)
def test_d1_interlock_never_accepted(fake, bad):
    with pytest.raises(ValueError):
        fake.run(interlock=bad)
    assert fake.calls == [] and not fake.output.exists()


@pytest.mark.parametrize("which", ["own", "intended"])
def test_fixed_branch_enforced(fake, which):
    bad = q.Source(
        "feature/robinhood-production-paper-history-recovery", "e" * 40, "f" * 40
    )
    with pytest.raises(ValueError):
        fake.run(
            source=bad if which == "own" else SOURCE,
            intended=bad if which == "intended" else INTENDED,
        )
    assert not fake.output.exists() and not fake.calls


@pytest.mark.parametrize("failure", [1, 2, 3, 4])
def test_source_admission_and_readmission_drift(fake, failure):
    fake.fail_at = failure
    with pytest.raises(ValueError):
        fake.run()
    assert fake.output.exists() == (failure > 2)


@pytest.mark.parametrize("field", ["budgets", "effects"])
@pytest.mark.parametrize("counter", q.COUNTERS)
@pytest.mark.parametrize("bad", [True, None, 0.0, 1])
def test_counter_exact_type_and_zero(fake, field, counter, bad):
    plan = q.Plan(SOURCE, INTENDED, NOW)
    records = [q.record(plan, event) for event in q.EVENTS]
    records[-1][field][counter] = bad
    with pytest.raises(ValueError):
        q.parse_authorization(b"".join(q.canonical(r) + b"\n" for r in records))


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "unknown",
        "missing",
        "bom",
        "crlf",
        "trailing",
        "nan",
        "empty",
        "partial",
        "authority",
        "target",
        "expiry",
        "policy",
        "strategy",
        "extra_counter",
        "missing_counter",
        "nested_unknown",
    ],
)
def test_closed_canonical_schema(fake, damage):
    fake.run()
    data = fake.output.read_bytes()
    rows = copy.deepcopy(q.parse_authorization(data))
    if damage == "duplicate":
        data = data.replace(b'"event":', b'"event":"FINAL","event":', 1)
    elif damage == "bom":
        data = b"\xef\xbb\xbf" + data
    elif damage == "crlf":
        data = data.replace(b"\n", b"\r\n")
    elif damage == "trailing":
        data += b" "
    elif damage == "nan":
        data = data.replace(b'"d1_invocations":0', b'"d1_invocations":NaN', 1)
    elif damage == "empty":
        data = b""
    elif damage == "partial":
        data = b"\n".join(data.splitlines()[:-1]) + b"\n"
    else:
        r = rows[0]
        if damage == "unknown":
            r["unknown"] = 0
        if damage == "missing":
            del r["authority"]
        if damage == "authority":
            r["authority"]["d1_execution_authorized"] = True
        if damage == "target":
            r["facts"]["target_session"] = "2026-10-20"
        if damage == "expiry":
            r["facts"]["authorization_expires_at"] = "2026-10-20T19:55:00+00:00"
        if damage == "policy":
            r["facts"]["d1_policy"]["starting_synthetic_cash"] = "9999"
        if damage == "strategy":
            r["facts"]["strategy_contract"]["symbol"] = "QQQ"
        if damage == "extra_counter":
            r["effects"]["other"] = 0
        if damage == "missing_counter":
            del r["budgets"]["d1_invocations"]
        if damage == "nested_unknown":
            r["facts"]["intended_d1"]["other"] = 0
        data = b"".join(q.canonical(r) + b"\n" for r in rows)
    with pytest.raises(ValueError):
        q.parse_authorization(data)


def test_slot_excludes_both_source_revisions_and_parameters(fake):
    a = q.Plan(SOURCE, INTENDED, NOW)
    b = q.Plan(
        replace(SOURCE, head="e" * 40, tree="f" * 40),
        replace(INTENDED, head="1" * 40, tree="2" * 40),
        NOW + timedelta(minutes=2),
    )
    assert a.name == b.name
    assert a.name != q.Plan(SOURCE, INTENDED, NOW + timedelta(days=1)).name
    fake.run()
    with pytest.raises(FileExistsError):
        fake.run(source=b.source, intended=b.intended_d1)


@pytest.mark.parametrize("initial", [b"", b"{", b"corrupt\n"])
def test_existing_ambiguous_artifact_is_consumed(fake, initial):
    fake.output.write_bytes(initial)
    with pytest.raises(FileExistsError):
        fake.run()
    assert fake.output.read_bytes() == initial


def test_concurrent_exclusive_reservation(fake):
    def run():
        try:
            return fake.run()
        except FileExistsError:
            return "COLLISION"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sorted(results) == sorted([q.READY, "COLLISION"])
    q.parse_authorization(fake.output.read_bytes())


@pytest.mark.parametrize("boundary", ["write", "flush", "fsync", "readback"])
@pytest.mark.parametrize("nth", range(1, 8))
def test_every_durable_boundary_consumes_slot(fake, monkeypatch, boundary, nth):
    counts = {"write": 0, "flush": 0, "fsync": 0, "readback": 0}
    fdopen, fsync, read = q.os.fdopen, q.os.fsync, q.read_evidence

    def trip(name):
        counts[name] += 1
        if boundary == name and counts[name] == nth:
            raise KeyboardInterrupt("modeled interruption")

    class Writer:
        def __init__(self, stream):
            self.stream = stream

        def fileno(self):
            return self.stream.fileno()

        def write(self, data):
            trip("write")
            return self.stream.write(data)

        def flush(self):
            trip("flush")
            return self.stream.flush()

        def close(self):
            return self.stream.close()

    def opened(fd, mode):
        stream = fdopen(fd, mode)
        return Writer(stream) if mode == "wb" else stream

    def synced(fd):
        trip("fsync")
        return fsync(fd)

    def reread(path, maximum, identity=None):
        if path == fake.output:
            trip("readback")
        return read(path, maximum, identity)

    monkeypatch.setattr(q.os, "fdopen", opened)
    monkeypatch.setattr(q.os, "fsync", synced)
    monkeypatch.setattr(q, "read_evidence", reread)
    with pytest.raises(KeyboardInterrupt):
        fake.run()
    assert fake.output.exists()
    reserved_bytes = fake.output.read_bytes()
    with pytest.raises(FileExistsError):
        fake.run()
    assert fake.output.read_bytes() == reserved_bytes
    assert counts[boundary] == nth


@pytest.mark.parametrize(
    "phase",
    [
        "close",
        "closed_read",
        "parse",
        "clock_expired",
        "clock_next_day",
        "roots",
        "predecessor_readmission",
    ],
)
def test_final_ambiguity_no_retry(fake, monkeypatch, phase):
    fdopen, read, parse = q.os.fdopen, q.read_evidence, q.parse_authorization
    calls = 0

    class Writer:
        def __init__(self, stream):
            self.stream = stream

        def fileno(self):
            return self.stream.fileno()

        def write(self, data):
            return self.stream.write(data)

        def flush(self):
            return self.stream.flush()

        def close(self):
            self.stream.close()
            raise OSError("ambiguous close")

    if phase == "close":
        monkeypatch.setattr(
            q.os,
            "fdopen",
            lambda fd, mode: (
                Writer(fdopen(fd, mode)) if mode == "wb" else fdopen(fd, mode)
            ),
        )
    if phase == "closed_read":

        def reread(path, maximum, identity=None):
            nonlocal calls
            if path == fake.output:
                calls += 1
                if calls == 8:
                    raise OSError("reread ambiguity")
            return read(path, maximum, identity)

        monkeypatch.setattr(q, "read_evidence", reread)
    if phase == "parse":
        monkeypatch.setattr(
            q,
            "parse_authorization",
            lambda _: (_ for _ in ()).throw(ValueError("parse ambiguity")),
        )
    if phase in ("clock_expired", "clock_next_day"):

        def clock():
            nonlocal calls
            calls += 1
            return (
                NOW
                if calls < 8
                else (
                    NOW.replace(hour=19, minute=55)
                    if phase == "clock_expired"
                    else NOW + timedelta(days=1)
                )
            )

        fake.clock = clock
    if phase in ("roots", "predecessor_readmission"):
        original_admit = fake.admit

        def admit(source):
            roots = original_admit(source)
            if len(fake.calls) == 3:
                if phase == "roots":
                    return (fake.parent / "other",)
                (fake.parent / q.D1R5.basename).write_bytes(b"corrupt")
            return roots

        fake.admit = admit
    with pytest.raises((ValueError, OSError)):
        fake.run()
    assert fake.output.exists()
    monkeypatch.setattr(q, "parse_authorization", parse)
    fake.clock = lambda: NOW
    # Restore predecessor only for the attempt to reach the already-consumed fence.
    (fake.parent / q.D1R5.basename).write_bytes(wake_payload())
    with pytest.raises(FileExistsError):
        fake.run()


@pytest.mark.parametrize("which", ["D1R5", "D1R6", "output"])
def test_hard_link_rejected(fake, which):
    path = (
        fake.output if which == "output" else fake.parent / getattr(q, which).basename
    )
    if which == "output":
        fake.run()
    os.link(path, fake.parent / "alias")
    with pytest.raises(ValueError):
        q.read_evidence(path, q.MAX_BYTES)
    if which != "output":
        with pytest.raises(ValueError):
            fake.run()
        assert not fake.output.exists()


def test_open_handle_substitution(fake, monkeypatch):
    path = fake.parent / q.D1R5.basename
    original = q.os.open
    replacement = fake.parent / "replacement"
    replacement.write_bytes(path.read_bytes())

    def opened(name, flags, *args):
        # Model pathname substitution between lstat and native open. Windows also
        # denies a physical rename while a CRT handle is already held open.
        return original(replacement if Path(name) == path else name, flags, *args)

    monkeypatch.setattr(q.os, "open", opened)
    with pytest.raises(ValueError, match="identity"):
        q.read_evidence(path, q.MAX_BYTES)


@pytest.mark.parametrize("reparse", [False, True])
def test_link_and_reparse_admission(fake, monkeypatch, reparse):
    original = Path.lstat
    path = fake.parent / q.D1R5.basename

    def metadata(self, *args, **kwargs):
        m = original(self, *args, **kwargs)
        if self == path:
            return SimpleNamespace(
                st_mode=m.st_mode if reparse else stat.S_IFLNK,
                st_file_attributes=0x400 if reparse else 0,
            )
        return m

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(ValueError):
        fake.run()
    assert not fake.output.exists()


@pytest.mark.parametrize(
    "option",
    [
        "--target-session",
        "--evidence",
        "--branch",
        "--policy",
        "--d1",
        "--prepare",
        "--execute",
    ],
)
def test_host_no_caller_semantics(option):
    with pytest.raises(ValueError):
        host.build_parser().parse_args([option, "2026-10-20"])


def test_host_uses_review_assertions_and_never_continues(monkeypatch, capsys):
    argv = [
        "--expected-head",
        SOURCE.head,
        "--expected-tree",
        SOURCE.tree,
        "--accepted-d1-head",
        INTENDED.head,
        "--accepted-d1-tree",
        INTENDED.tree,
    ]
    calls = []
    monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda _: q.INTERLOCK)

    def publish(runtime, source, intended, interlock):
        calls.append((type(runtime), source, intended, interlock))
        return q.READY

    monkeypatch.setattr(q, "publish_prerequisite", publish)
    assert host.main(argv) == 0
    assert calls == [(host.EvidenceRuntime, SOURCE, INTENDED, q.INTERLOCK)]
    assert capsys.readouterr().out.strip() == q.READY
    monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    assert host.main(argv) == 2 and len(calls) == 1


def test_import_and_reachable_call_containment():
    # Explicit public parser imports, never the operational D1R6 host/runtime.
    tree = ast.parse(Path(q.__file__).read_text())
    imported = {
        n.module: {a.name for a in n.names}
        for n in tree.body
        if isinstance(n, ast.ImportFrom)
    }
    assert imported["trading_bot.review_paper.pre_market_wake_overnight"] == {
        "parse_arm",
        "plan_from_facts",
    }
    assert imported["trading_bot.review_paper.pre_market_wake_qualification"] == {
        "parse_wake_journal",
        "validate_source_identity",
    }
    allowed_project = {
        "trading_bot.domain",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.pre_market_wake_overnight",
        "trading_bot.review_paper.pre_market_wake_qualification",
        "trading_bot.strategies.moving_average",
        "trading_bot.strategies.production",
    }
    assert {m for m in imported if m.startswith("trading_bot")} == allowed_project
    forbidden = {
        "reconcile",
        "load_launch_authority",
        "load_armed",
        "_WindowsRuntime",
        "observe",
        "principal",
        "create",
        "child",
        "evaluate",
        "generate_signal",
        "prepare",
        "execute",
        "run_armed_production_paper_session",
        "sleep",
        "CredReadW",
        "CredWriteW",
        "connect",
        "urlopen",
        "Popen",
        "eval",
        "exec",
        "__import__",
        "import_module",
        "environ",
        "getenv",
    }
    # Traverse reachable parser/helper/class calls from the public entry points.
    for module, entries in (
        (arm, {"parse_arm", "plan_from_facts"}),
        (wake, {"parse_wake_journal"}),
        (q, {"publish_prerequisite"}),
    ):
        t = ast.parse(Path(module.__file__).read_text())
        definitions = {
            n.name: n for n in t.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
        }
        pending, seen = list(entries), set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            for n in ast.walk(definitions[name]):
                if isinstance(n, ast.Call):
                    target = (
                        n.func.id
                        if isinstance(n.func, ast.Name)
                        else n.func.attr
                        if isinstance(n.func, ast.Attribute)
                        else ""
                    )
                    assert target not in forbidden, (module.__name__, name, target)
                    if target in definitions:
                        pending.append(target)
        assert entries <= seen
    ht = ast.parse(Path(host.__file__).read_text())
    assert {n.name for n in ht.body if isinstance(n, ast.ClassDef)} == {
        "EvidenceRuntime",
        "_Parser",
    }
    for n in ast.walk(ht):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr not in forbidden
    # Closed subprocess transport: only read-only Git with fixed operation tokens.
    git_node = next(
        n for n in ht.body if isinstance(n, ast.FunctionDef) and n.name == "_git"
    )
    assert [
        n.func.attr
        for n in ast.walk(git_node)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ] == ["strip", "run"]


def test_checkpoint_profile_inventory_and_frozen_authority():
    spec = runner._checkpoint_specs()[q.CHECKPOINT]
    assert spec.remote_branch == q.BRANCH and spec.preflight is spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), q.BRANCH, "push")
        == q.CHECKPOINT
    )
    assert runner.resolve_ci_certification_profile(q.CHECKPOINT) == "robinhood"
    assert runner._arch134_d1r7_authority_check(ROOT) == ()
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 78
    inventory = certification.discover_inventory(ROOT)
    assert {
        p: len(certification.select_inventory(inventory, p))
        for p in certification.PROFILES
    } == {"full": 201, "robinhood": 112, "legacy": 222, "exhaustive": 423}
    assert len([p for p in inventory if p.startswith("tests/gui/")]) == 51
    for name, expected in runner.ARCH134_D1R7_PREDECESSOR_DIGESTS.items():
        assert (
            hashlib.sha256(q.canonical(getattr(runner, name))).hexdigest() == expected
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "executable", "wrong", "predecessor"]
)
def test_successor_overlay_fails_closed(monkeypatch, mutation):
    pins = dict(runner.ARCH134_D1R7_TEST_PIN_OVERRIDES)
    path = next(iter(pins))
    previous = runner.ARCH134_D1R7_PREDECESSOR_TEST_PINS[path]
    if mutation == "missing":
        pins.pop(path)
    if mutation == "extra":
        pins["tests/unknown.py"] = "a" * 40
    if mutation == "executable":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    if mutation == "wrong":
        pins[path] = "a" * 40
    monkeypatch.setattr(runner, "ARCH134_D1R7_TEST_PIN_OVERRIDES", pins)
    if mutation == "predecessor":
        previous = "f" * 40
    with pytest.raises(ValueError):
        runner._arch134_d1r7_test_pin(path, previous)


def test_frozen_workflow_fallback_and_dynamic_successor():
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert runner._batch_workflow_is_reviewed(workflow)
    assert q.CHECKPOINT not in workflow
    assert not runner._batch_workflow_is_reviewed(
        workflow.replace("arch134-d1r5-pre-market-wake-qualification", q.CHECKPOINT)
    )


@pytest.mark.parametrize("intended", [False, True])
@pytest.mark.parametrize(
    "drift",
    [
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
        "mixed_path",
        "roots",
    ],
)
def test_host_admission_proves_fixed_local_tracking_live_identity(
    monkeypatch, intended, drift
):
    monkeypatch.setattr(host, "WORKTREE", ROOT)
    target = ROOT.parent / "future-source-test-only"
    monkeypatch.setattr(host, "D1_WORKTREE", target)
    source = INTENDED if intended else SOURCE
    root = target if intended else ROOT
    branch = source.branch
    values = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): branch,
        ("rev-parse", "HEAD"): source.head,
        ("rev-parse", "HEAD^{tree}"): source.tree,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("remote", "get-url", "origin"): q.ORIGIN,
        ("remote", "get-url", "--push", "origin"): q.ORIGIN,
        ("rev-parse", "--symbolic-full-name", "@{upstream}"): "refs/remotes/origin/"
        + branch,
        ("rev-parse", "origin/" + branch): source.head,
        ("rev-parse", "origin/" + branch + "^{tree}"): source.tree,
        ("ls-remote", "origin", "refs/heads/" + branch): source.head
        + "\trefs/heads/"
        + branch,
        ("worktree", "list", "--porcelain"): f"worktree {ROOT}\n\nworktree {target}\n",
    }
    keys = list(values)
    bad = {
        "root": 0,
        "branch": 1,
        "head": 2,
        "tree": 3,
        "dirty": 4,
        "origin": 5,
        "push_origin": 6,
        "upstream": 7,
        "tracking_head": 8,
        "tracking_tree": 9,
        "live": 10,
        "registry": 11,
    }
    if drift in bad:
        values[keys[bad[drift]]] = "drift"
    if drift == "mixed_file":
        monkeypatch.setitem(
            host.sys.modules,
            "trading_bot.test_only_mixed",
            SimpleNamespace(__file__=str(target / "foreign.py")),
        )
    if drift == "mixed_path":
        monkeypatch.setitem(
            host.sys.modules,
            "trading_bot.test_only_mixed",
            SimpleNamespace(
                __file__=str(ROOT / "src/trading_bot/__init__.py"),
                __path__=[str(target / "foreign")],
            ),
        )
    calls = []

    def git(where, *args):
        assert where == root
        calls.append(args)
        return values[args]

    monkeypatch.setattr(host, "_git", git)
    if drift == "roots":
        assert host.admit_source(source) == (ROOT, target)
    else:
        with pytest.raises(ValueError):
            host.admit_source(source)
    assert calls and all(
        c[0] in {"rev-parse", "branch", "status", "remote", "ls-remote", "worktree"}
        for c in calls
    )


@pytest.mark.parametrize(
    "phase",
    [
        "short_write",
        "fdopen",
        "empty_reservation",
        "changed_readback",
        "output_hardlink",
        "output_reparse",
    ],
)
def test_reservation_and_output_identity_ambiguity(fake, monkeypatch, phase):
    opened, read, fsync, fdopen = q.os.open, q.read_evidence, q.os.fsync, q.os.fdopen
    fired = False

    class Writer:
        def __init__(self, stream):
            self.stream = stream

        def fileno(self):
            return self.stream.fileno()

        def write(self, data):
            self.stream.write(data[:-1])
            return len(data) - 1

        def close(self):
            return self.stream.close()

    if phase in ("short_write", "fdopen"):

        def wrap(fd, mode):
            if mode == "wb":
                if phase == "fdopen":
                    os.close(fd)
                    raise OSError("fdopen ambiguity")
                return Writer(fdopen(fd, mode))
            return fdopen(fd, mode)

        monkeypatch.setattr(q.os, "fdopen", wrap)
    if phase == "empty_reservation":

        def reserve(path, flags, *args):
            fd = opened(path, flags, *args)
            if flags & os.O_EXCL:
                os.close(fd)
                raise OSError("reservation acknowledgement lost")
            return fd

        monkeypatch.setattr(q.os, "open", reserve)
    if phase == "changed_readback":

        def changed(path, maximum, identity=None):
            payload = read(path, maximum, identity)
            return payload + b" " if path == fake.output else payload

        monkeypatch.setattr(q, "read_evidence", changed)
    if phase == "output_hardlink":

        def synced(fd):
            nonlocal fired
            fsync(fd)
            if not fired:
                fired = True
                os.link(fake.output, fake.parent / "output-alias")

        monkeypatch.setattr(q.os, "fsync", synced)
    if phase == "output_reparse":
        original = Path.lstat

        def metadata(self, *args, **kwargs):
            m = original(self, *args, **kwargs)
            if self == fake.output:
                return SimpleNamespace(st_mode=m.st_mode, st_file_attributes=0x400)
            return m

        monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises((OSError, ValueError)):
        fake.run()
    assert fake.output.exists()
    reserved_bytes = fake.output.read_bytes()
    with pytest.raises((FileExistsError, ValueError)):
        fake.run()
    assert fake.output.read_bytes() == reserved_bytes


def test_complete_fixed_policy_literal():
    assert q.fixed_policy() == {
        "starting_synthetic_cash": "10000",
        "opening_buffer_seconds": 300,
        "closing_buffer_seconds": 300,
        "max_quote_age_seconds": 60,
        "max_snapshot_age_seconds": 600,
        "risk_limits": {
            "max_position_percent": "0.20",
            "max_total_exposure_percent": "0.80",
            "max_order_notional": None,
            "max_new_position_percent": None,
            "minimum_cash_reserve_percent": "0.10",
            "allow_fractional_shares": True,
            "fractional_increment": "0.001",
            "allow_buying": True,
            "allow_selling": True,
            "estimated_commission": "0",
        },
        "synthetic_execution": {
            "order_type": "MARKET",
            "time_in_force": "DAY",
            "slippage_basis_points": "0",
            "commission": "0",
            "broker_placement_budget": 0,
            "maximum_synthetic_paper_fills": 1,
        },
    }


def test_exact_zero_effect_surface():
    assert set(q.COUNTERS) == set(
        """d1_invocations d1r5_invocations alpaca_requests
        provider_requests credential_reads credential_writes oauth_interactions
        robinhood_reads robinhood_reviews strategy_evaluations prepare_attempts
        execute_attempts paper_mutations broker_placements scheduler_reads
        scheduler_creates scheduler_updates scheduler_runs scheduler_deletes
        acl_mutations d2_invocations live_effects production_sqlite_reads
        production_sqlite_writes armed_session_store_reads armed_session_store_writes
        review_paper_store_reads review_paper_store_writes""".split()
    )
    assert len(q.COUNTERS) == 28
    assert q.AUTHORITY == (
        "d1_execution_authorized",
        "prepare_authorized",
        "execute_authorized",
    )


def test_d1r6_resolution_runs_once_before_d1r7_successor():
    path = "tests/runtime/checkpoint_runner/test_core.py"
    predecessor = runner.ARCH134_D1R5_TEST_PIN_OVERRIDES[path]
    resolved = runner._arch134_d1r6_test_pin(path, predecessor)
    with pytest.raises(ValueError, match="predecessor resolution drift"):
        runner._arch134_d1r6_test_pin(path, resolved)
    current = runner._arch134_f1_current_inventory_test_pin(
        path, runner._arch134_d1r7_test_pin(path, resolved)
    )
    assert current == runner._git_blob_sha1(ROOT / path)
    assert runner._arch134_d1r6_authority_check(ROOT) == ()
