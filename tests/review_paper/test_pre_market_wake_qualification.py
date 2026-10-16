"""D1R5 fake clocks/source and temporary journals only; never real sleep."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.review_paper import pre_market_wake_qualification as q
from trading_bot.review_paper import pre_market_wake_qualification_host as host

HEAD, TREE = "a" * 40, "b" * 40
OPEN = datetime(2026, 10, 14, 13, 30, tzinfo=UTC)
ADMISSION = OPEN + timedelta(minutes=5)


class Fake:
    def __init__(self, root: Path, start: datetime, wake: datetime) -> None:
        self.root = root
        self.now = start
        self.wake = wake
        self.sleep_calls: list[float] = []
        self.source_calls = 0
        self.fail_source = 0
        self.evidence = root.parent / "wake.jsonl"

    def source(self) -> tuple[Path, ...]:
        self.source_calls += 1
        if self.source_calls == self.fail_source:
            raise RuntimeError("SECRET source error")
        return (self.root,)

    def sleep(self, seconds: float) -> None:
        # Independently read bytes at the sleeper boundary: WAITING is durable.
        records = q.parse_wake_journal(self.evidence.read_bytes())
        assert records[-1]["event"] == "WAITING_FOR_MARKET"
        self.sleep_calls.append(seconds)
        self.now = self.wake

    def run(self, **overrides) -> q.WakeClassification:
        args = dict(
            expected_head=HEAD,
            expected_tree=TREE,
            qualify_wake=q.QUALIFY_WAKE_INTERLOCK,
            evidence=self.evidence,
            admit_source=self.source,
            clock=lambda: self.now,
            sleeper=self.sleep,
        )
        return q.qualify_pre_market_wake(**(args | overrides))


@pytest.fixture
def fake(tmp_path: Path) -> Fake:
    root = tmp_path / "repo"
    root.mkdir()
    return Fake(root, OPEN - timedelta(minutes=10), ADMISSION)


@pytest.mark.parametrize("offset", [-900, -600, -1, 0, 120, 299, 299.999999])
@pytest.mark.parametrize("lateness", [0, 1, 60])
def test_one_wait_then_timely_pass(fake: Fake, offset: float, lateness: int) -> None:
    fake.now = OPEN + timedelta(seconds=offset)
    fake.wake = ADMISSION + timedelta(seconds=lateness)
    assert fake.run() is q.WakeClassification.PASS
    assert fake.sleep_calls == [
        (ADMISSION - (OPEN + timedelta(seconds=offset))).total_seconds()
    ]
    assert fake.source_calls == 3
    records = q.parse_wake_journal(fake.evidence.read_bytes())
    assert tuple(r["event"] for r in records) == (
        "QUALIFICATION_RESERVED",
        "SOURCE_ADMITTED",
        "WAITING_FOR_MARKET",
        "WAKE_OBSERVED",
        "SOURCE_READMITTED",
        "FINAL",
    )
    assert records[-1]["classification"] == "PASS"
    assert records[-1]["source_readmitted"] is True
    assert all(
        type(r[k]) is int and r[k] == 0 for r in records for k in q.EFFECT_COUNTERS
    )
    assert q.serialize_wake_journal(records) == fake.evidence.read_bytes()


@pytest.mark.parametrize(
    "start",
    [
        OPEN - timedelta(minutes=15, microseconds=1),
        ADMISSION,
        ADMISSION + timedelta(seconds=1),
        OPEN.replace(hour=19, minute=55),
        OPEN.replace(hour=20, minute=0),
    ],
)
def test_rejected_start_never_reserves_or_sleeps(fake: Fake, start: datetime) -> None:
    fake.now = start
    assert fake.run() is q.WakeClassification.START_WINDOW_REJECTED
    assert not fake.evidence.exists()
    assert fake.sleep_calls == []


@pytest.mark.parametrize(
    "start",
    [
        OPEN.replace(day=17),
        OPEN.replace(month=11, day=26),
        OPEN.replace(year=2029),
    ],
)
def test_missing_or_unsupported_session(fake: Fake, start: datetime) -> None:
    fake.now = start
    assert fake.run() is q.WakeClassification.SESSION_UNAVAILABLE
    assert not fake.evidence.exists() and not fake.sleep_calls


def test_wrong_schedule_date_cannot_be_admitted(fake: Fake, monkeypatch) -> None:
    schedule = q.NYSEPublishedRegularSessionAuthority().schedule_for(
        (OPEN + timedelta(days=1)).date()
    )
    monkeypatch.setattr(
        q.NYSEPublishedRegularSessionAuthority, "schedule_for", lambda *a: schedule
    )
    assert fake.run() is q.WakeClassification.START_WINDOW_REJECTED
    assert not fake.evidence.exists()


@pytest.mark.parametrize(
    "awake,expected",
    [
        (ADMISSION - timedelta(microseconds=1), "WAKE_TOO_EARLY"),
        (ADMISSION + timedelta(seconds=60, microseconds=1), "WAKE_TOO_LATE"),
        (ADMISSION + timedelta(days=1), "WAKE_SESSION_INVALID"),
        (OPEN.replace(hour=19, minute=55), "WAKE_SESSION_INVALID"),
        (OPEN.replace(hour=20, minute=0), "WAKE_SESSION_INVALID"),
    ],
)
def test_bad_wake_stops_after_one_wait(fake: Fake, awake, expected) -> None:
    fake.wake = awake
    assert fake.run().value == expected
    assert len(fake.sleep_calls) == 1 and fake.source_calls == 2
    assert (
        q.parse_wake_journal(fake.evidence.read_bytes())[-1]["classification"]
        == expected
    )


def test_sleeper_returns_without_advancing_time(fake: Fake) -> None:
    fake.wake = fake.now
    assert fake.run() is q.WakeClassification.WAKE_TOO_EARLY
    assert len(fake.sleep_calls) == 1


@pytest.mark.parametrize("call", [1, 2, 3])
def test_source_drift_at_every_boundary(fake: Fake, call: int) -> None:
    fake.fail_source = call
    assert fake.run() is q.WakeClassification.SOURCE_REJECTED
    assert len(fake.sleep_calls) == int(call == 3)
    if call == 1:
        assert not fake.evidence.exists()
    else:
        payload = fake.evidence.read_bytes()
        assert b"SECRET" not in payload
        assert q.parse_wake_journal(payload)[-1]["classification"] == "SOURCE_REJECTED"


def test_clock_rechecked_after_source_admission_overhead(fake: Fake) -> None:
    original = fake.source

    def source():
        roots = original()
        if fake.source_calls == 2:
            fake.now += timedelta(seconds=7)
        return roots

    assert fake.run(admit_source=source) is q.WakeClassification.PASS
    assert fake.sleep_calls == [893.0]


def test_admission_opens_during_source_check_blocks_without_wait(fake: Fake) -> None:
    original = fake.source

    def source():
        roots = original()
        if fake.source_calls == 2:
            fake.now = ADMISSION
        return roots

    assert fake.run(admit_source=source) is q.WakeClassification.START_WINDOW_REJECTED
    assert not fake.sleep_calls
    assert q.parse_wake_journal(fake.evidence.read_bytes())[-1]["event"] == "FINAL"


def test_sleeper_exception_sanitized_and_not_retried(fake: Fake) -> None:
    def sleeper(seconds):
        fake.sleep_calls.append(seconds)
        raise RuntimeError("SECRET sleeper error")

    assert fake.run(sleeper=sleeper) is q.WakeClassification.WAIT_FAILED
    assert len(fake.sleep_calls) == 1
    payload = fake.evidence.read_bytes()
    assert b"SECRET" not in payload
    assert q.parse_wake_journal(payload)[-1]["classification"] == "WAIT_FAILED"


def test_interrupt_consumes_durable_wait_and_forbids_reuse(fake: Fake) -> None:
    def sleeper(seconds):
        fake.sleep(seconds)
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        fake.run(sleeper=sleeper)
    consumed = fake.evidence.read_bytes()
    assert q.parse_wake_journal(consumed)[-1]["event"] == "WAITING_FOR_MARKET"
    fake.now = OPEN - timedelta(minutes=10)
    with pytest.raises(ValueError, match="destination"):
        fake.run()
    assert fake.evidence.read_bytes() == consumed and len(fake.sleep_calls) == 1


def test_collision_preserves_existing_bytes(fake: Fake) -> None:
    fake.evidence.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        fake.run()
    assert fake.evidence.read_bytes() == b"preserve" and not fake.sleep_calls


def test_exclusive_reservation_closes_collision_race(fake: Fake, monkeypatch) -> None:
    original = q.admit_wake_evidence

    def collision(path, roots):
        admitted = original(path, roots)
        admitted.write_bytes(b"race")
        return admitted

    monkeypatch.setattr(q, "admit_wake_evidence", collision)
    with pytest.raises(FileExistsError):
        fake.run()
    assert fake.evidence.read_bytes() == b"race" and not fake.sleep_calls


@pytest.mark.parametrize(
    "kind", ["internal", "relative", "missing-parent", "suffix", "no-roots"]
)
def test_evidence_path_rejections(fake: Fake, kind: str) -> None:
    path, roots = fake.evidence, (fake.root,)
    if kind == "internal":
        path = fake.root / "wake.jsonl"
    elif kind == "relative":
        path = Path("wake.jsonl")
    elif kind == "missing-parent":
        path = fake.evidence.parent / "missing" / "wake.jsonl"
    elif kind == "suffix":
        path = path.with_suffix(".json")
    else:
        roots = ()
    with pytest.raises(ValueError):
        q.admit_wake_evidence(path, roots)


def test_reparse_parent_rejected(fake: Fake, monkeypatch) -> None:
    original = Path.lstat

    def metadata(path, *args, **kw):
        info = original(path, *args, **kw)
        if path == fake.evidence.parent:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(ValueError, match="linked"):
        fake.run()
    assert not fake.sleep_calls


def test_symlink_parent_rejected(fake: Fake, monkeypatch) -> None:
    original = Path.lstat

    def metadata(path, *args, **kw):
        if path == fake.evidence.parent:
            return SimpleNamespace(st_mode=0o120777, st_file_attributes=0)
        return original(path, *args, **kw)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(ValueError, match="linked"):
        fake.run()


@pytest.mark.parametrize("phase", ["write", "flush", "fsync"])
def test_durability_failure_never_sleeps(fake: Fake, monkeypatch, phase: str) -> None:
    original = Path.open

    class Broken:
        def __init__(self, output):
            self.output = output

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.output.close()

        def write(self, payload):
            if phase == "write":
                return 0
            return self.output.write(payload)

        def flush(self):
            if phase == "flush":
                raise OSError("SECRET flush")
            return self.output.flush()

        def fileno(self):
            return self.output.fileno()

    monkeypatch.setattr(
        Path, "open", lambda path, *a, **kw: Broken(original(path, *a, **kw))
    )
    if phase == "fsync":
        monkeypatch.setattr(
            q.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("SECRET fsync"))
        )
    with pytest.raises((ValueError, OSError)):
        fake.run()
    assert fake.source_calls == 1 and not fake.sleep_calls


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "duplicate",
        "bool",
        "source",
        "order",
        "window",
        "date",
        "start",
        "wait",
        "wake",
        "readmitted",
        "classification",
        "counter",
        "changed-fact",
        "bom",
        "trailing",
        "whitespace",
        "no-newline",
        "oversized",
        "nan",
        "terminal-extra",
        "truncated-line",
    ],
)
def test_canonical_parser_rejects_invalid_material(fake: Fake, mutation: str) -> None:
    assert fake.run() is q.WakeClassification.PASS
    payload = fake.evidence.read_bytes()
    records = [json.loads(line) for line in payload.splitlines()]
    if mutation == "unknown":
        records[0]["SECRET"] = "SECRET"
    elif mutation == "missing":
        del records[0]["source_head"]
    elif mutation == "bool":
        records[0][q.EFFECT_COUNTERS[0]] = False
    elif mutation == "source":
        records[0]["source_head"] = "0" * 40
    elif mutation == "order":
        records[1]["event"] = "WAKE_OBSERVED"
    elif mutation == "window":
        records[0]["admission_opens_at"] = OPEN.isoformat()
    elif mutation == "date":
        records[0]["target_session"] = "2026-10-17"
    elif mutation == "start":
        records[0]["start_observed_at"] = ADMISSION.isoformat()
    elif mutation == "wait":
        records[2]["wait_seconds"] = 901.0
    elif mutation == "wake":
        records[3]["wake_observed_at"] = None
    elif mutation == "readmitted":
        records[4]["source_readmitted"] = 1
    elif mutation == "classification":
        records[-1]["classification"] = "WAIT_FAILED"
    elif mutation == "counter":
        records[-1]["provider_requests"] = 1
    elif mutation == "changed-fact":
        records[-1]["source_head"] = "c" * 40
    elif mutation == "nan":
        records[2]["wait_seconds"] = float("nan")
    elif mutation == "terminal-extra":
        records.append(records[-1])
    payload = b"".join(
        (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for r in records
    )
    if mutation == "duplicate":
        payload = payload.replace(b'"event":', b'"event":"SECRET","event":', 1)
    elif mutation == "bom":
        payload = b"\xef\xbb\xbf" + payload
    elif mutation == "trailing":
        payload += b"SECRET"
    elif mutation == "whitespace":
        payload = b" " + payload
    elif mutation == "no-newline":
        payload = payload[:-1]
    elif mutation == "oversized":
        payload = b"SECRET" * q.MAX_JOURNAL_BYTES
    elif mutation == "truncated-line":
        payload = payload[:-10]
    with pytest.raises(ValueError, match="invalid canonical") as error:
        q.parse_wake_journal(payload)
    assert "SECRET" not in str(error.value) and error.value.__context__ is None


def test_every_durable_prefix_is_consumed_parseable_evidence(fake: Fake) -> None:
    fake.run()
    records = q.parse_wake_journal(fake.evidence.read_bytes())
    for length in range(1, 7):
        prefix = records[:length]
        assert q.parse_wake_journal(q.serialize_wake_journal(prefix)) == prefix


@pytest.mark.parametrize(
    "option",
    [
        "--symbol",
        "--session-date",
        "--exchange",
        "--open-time",
        "--buffer",
        "--wait-duration",
        "--wake-deadline",
        "--provider",
        "--credential-target",
        "--robinhood-endpoint",
        "--strategy",
        "--quantity",
        "--side",
        "--price",
        "--runtime-database",
        "--arm",
        "--expected-h",
    ],
)
def test_host_rejects_semantic_or_abbreviated_inputs(option, capsys) -> None:
    assert (
        host.main(
            [
                "--expected-head",
                HEAD,
                "--expected-tree",
                TREE,
                "--evidence",
                "fake.jsonl",
                "--qualify-wake",
                q.QUALIFY_WAKE_INTERLOCK,
                option,
                "SECRET",
            ]
        )
        == 2
    )
    assert capsys.readouterr().err == "PRE_MARKET_WAKE_QUALIFICATION_HOST_BLOCKED\n"


@pytest.mark.parametrize("error", [RuntimeError("SECRET"), KeyboardInterrupt()])
def test_host_errors_are_fixed_text(monkeypatch, capsys, error) -> None:
    def fail(**kw):
        raise error

    monkeypatch.setattr(host, "qualify_pre_market_wake", fail)
    assert (
        host.main(
            [
                "--expected-head",
                HEAD,
                "--expected-tree",
                TREE,
                "--evidence",
                "fake.jsonl",
                "--qualify-wake",
                q.QUALIFY_WAKE_INTERLOCK,
            ]
        )
        == 2
    )
    assert capsys.readouterr().err == "PRE_MARKET_WAKE_QUALIFICATION_HOST_BLOCKED\n"


def test_import_and_help_do_not_import_credentials_or_execute_effects() -> None:
    root = Path(__file__).resolve().parents[2]
    code = """
import sys, time, subprocess, sqlite3
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs):
    raise AssertionError('effect during import/help')
time.sleep = subprocess.run = sqlite3.connect = forbidden
from trading_bot.review_paper import pre_market_wake_qualification_host as host
assert not any('credential' in name or 'oauth' in name or 'armed_session' in name
               for name in sys.modules if name.startswith('trading_bot.'))
try:
    host.main(['--help'])
except SystemExit as result:
    assert result.code == 0
else:
    raise AssertionError('help did not exit')
"""
    result = subprocess.run(
        [sys.executable, "-B", "-", str(root / "src")],
        input=code,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_host_composes_only_clock_sleep_and_qualifier(
    fake: Fake, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(host, "admit_wake_source", lambda *a: fake.source())
    monkeypatch.setattr(host.time, "sleep", fake.sleep)
    monkeypatch.setattr(host, "datetime", SimpleNamespace(now=lambda tz: fake.now))
    assert (
        host.main(
            [
                "--expected-head",
                HEAD,
                "--expected-tree",
                TREE,
                "--evidence",
                str(fake.evidence),
                "--qualify-wake",
                q.QUALIFY_WAKE_INTERLOCK,
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == "PRE_MARKET_WAKE_QUALIFICATION_PASS\n"


@pytest.mark.parametrize(
    "boundary",
    [
        "root",
        "branch",
        "head",
        "tree",
        "dirty",
        "origin",
        "tracking-head",
        "tracking-tree",
        "remote",
        "mixed-import",
        "worktree-list",
    ],
)
def test_exact_source_admission_fails_closed(monkeypatch, boundary: str) -> None:
    root = Path(host.__file__).resolve().parents[3]
    monkeypatch.setattr(host, "WORKTREE", root)
    monkeypatch.setattr(host.os, "name", "nt")
    responses = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): host.BRANCH,
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("remote", "get-url", "origin"): host.ORIGIN,
        ("rev-parse", "origin/" + host.BRANCH): HEAD,
        ("rev-parse", "origin/" + host.BRANCH + "^{tree}"): TREE,
        ("ls-remote", "origin", "refs/heads/" + host.BRANCH): HEAD
        + "\trefs/heads/"
        + host.BRANCH,
        ("worktree", "list", "--porcelain"): "worktree " + str(root),
    }
    keys = list(responses)
    if boundary == "mixed-import":
        monkeypatch.setitem(
            sys.modules,
            "trading_bot.fake_mixed",
            SimpleNamespace(__file__=str(root.parent / "mixed.py")),
        )
    else:
        responses[
            keys[
                [
                    "root",
                    "branch",
                    "head",
                    "tree",
                    "dirty",
                    "origin",
                    "tracking-head",
                    "tracking-tree",
                    "remote",
                    "worktree-list",
                ].index(boundary)
            ]
        ] = "mismatch"
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda argv, **kw: SimpleNamespace(stdout=responses[tuple(argv[3:])]),
    )
    with pytest.raises(ValueError):
        host.admit_wake_source(HEAD, TREE)


def test_d1r5_registration_and_authority() -> None:
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH134_D1R5_NAME]
    assert spec.remote_branch == host.BRANCH
    assert spec.preflight is None and spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), host.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner._arch134_d1r5_authority_check(root) == ()


def test_unreviewed_successor_overlay_path_fails_closed(monkeypatch) -> None:
    from scripts import checkpoint_runner as runner

    monkeypatch.setattr(
        runner,
        "ARCH134_D1R5_TEST_PIN_OVERRIDES",
        runner.ARCH134_D1R5_TEST_PIN_OVERRIDES
        | {"src/trading_bot/review_paper/armed_session.py": "a" * 40},
    )
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch134_d1r5_authority_check(root)
    assert runner._arch134_authentication_authority_check(root)


def test_source_import_closure_has_no_operational_modules() -> None:
    allowed = {
        "__future__",
        "json",
        "os",
        "stat",
        "collections.abc",
        "datetime",
        "enum",
        "pathlib",
        "typing",
        "zoneinfo",
        "argparse",
        "subprocess",
        "sys",
        "time",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.session_admission",
        "trading_bot.review_paper.pre_market_wake_qualification",
    }
    for module in (q, host):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = {
            n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        } | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        }
        assert imports <= allowed
