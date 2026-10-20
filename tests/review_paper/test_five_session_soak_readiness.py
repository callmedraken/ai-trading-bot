"""F2 fake/static/disposable tests: never inspect the operational host."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.review_paper.test_d1_session_authorization import arm_payload, wake_payload

from scripts import checkpoint_runner as runner
from trading_bot.review_paper import five_session_soak_readiness as f

ROOT = Path(__file__).resolve().parents[2]


class Fake(f.ReadOnlyHost):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.drift = None
        self.now = datetime(2026, 10, 20, 13, tzinfo=UTC)

    def edge(self, name, value):
        self.calls.append(name)
        if self.drift == name and self.calls.count(name) == 2:
            raise ValueError("private S-1-5-21 token account provider body")
        return value

    def clock(self):
        return self.now

    def f2_source(self):
        return self.edge("f2", ("a" * 40, "b" * 40))

    def sources(self):
        self.observations["git_commands"] += 1
        return self.edge("sources", ("registry", (1, 2)))

    def predecessors(self):
        self.observations["predecessor_reads"] += 2
        return self.edge("predecessors", (1, "accepted"))

    def runtime(self):
        self.observations["runtime_inspections"] += 1
        return self.edge("runtime", ((3, 4), "same bytes"))

    def namespace(self):
        self.observations["filesystem_observations"] += 1
        return self.edge("namespace", (1, 2))

    def scheduler(self):
        self.observations["scheduler_observations"] += 1
        return self.edge("scheduler", None)


@pytest.fixture
def fake(monkeypatch):
    host = Fake()
    monkeypatch.setattr(f, "ReadOnlyHost", lambda: host)
    return host


def test_ready_is_closed_diagnostic_only(fake):
    result = f.preflight()
    f.validate_result(result)
    assert set(result) == f.FIELDS
    assert result["status"] == f.READY
    assert result["paper_records"] == 3 and result["session_reservations"] == 4
    assert result["preview_targets"] == [
        "2026-10-20",
        "2026-10-21",
        "2026-10-22",
        "2026-10-23",
        "2026-10-26",
    ]
    assert fake.calls == [
        "f2",
        "sources",
        "predecessors",
        "runtime",
        "namespace",
        "scheduler",
        "sources",
        "predecessors",
        "runtime",
        "namespace",
        "scheduler",
        "f2",
    ]
    assert all(type(v) is int and v == 0 for v in result["effects"].values())
    assert all(v > 0 for v in result["observations"].values())
    for key in (
        "runtime_write_readiness",
        "credential_readiness",
        "provider_readiness",
    ):
        assert result[key] == "NOT_CHECKED"


@pytest.mark.parametrize(
    "edge", ["f2", "sources", "predecessors", "runtime", "namespace", "scheduler"]
)
def test_final_readmission_blocks_every_drift(fake, edge):
    fake.drift = edge
    result = f.preflight()
    assert result["status"] == "BLOCKED"
    f.validate_result(result)
    assert "private" not in json.dumps(result) and "S-1-5" not in json.dumps(result)
    assert fake.calls.count(edge) == 2  # No retries or repair.
    assert not any(result["effects"].values())


def test_same_status_changed_snapshot_blocks(fake):
    calls = []

    def runtime():
        calls.append(1)
        return ((3, 4), "first" if len(calls) == 1 else "changed bytes")

    fake.runtime = runtime
    assert f.preflight()["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "bad",
    [datetime(2026, 10, 20), "2026-10-20", None, datetime(2029, 1, 1, tzinfo=UTC)],
)
def test_bad_clock_and_unsupported_manifest_block(fake, bad):
    fake.now = bad
    assert f.preflight()["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "at,first",
    [
        ("2026-10-20T19:54:59+00:00", "2026-10-20"),
        ("2026-10-20T19:55:00+00:00", "2026-10-21"),
        ("2026-10-24T15:00:00+00:00", "2026-10-26"),
        ("2026-11-26T15:00:00+00:00", "2026-11-27"),
        ("2026-11-27T17:54:59+00:00", "2026-11-27"),
        ("2026-11-27T17:55:00+00:00", "2026-11-30"),
        ("2026-03-06T20:55:00+00:00", "2026-03-09"),
        ("2026-11-02T20:54:59+00:00", "2026-11-02"),
    ],
)
def test_preview_published_window_no_authority(fake, at, first):
    fake.now = datetime.fromisoformat(at)
    result = f.preflight()
    assert result["status"] == f.READY
    assert len(result["preview_targets"]) == 5
    assert result["preview_targets"][0] == first
    assert not any(result["effects"].values())


@pytest.mark.parametrize("field", sorted(f.FIELDS))
def test_result_rejects_missing_unknown_and_noncanonical(fake, field):
    good = f.preflight()
    missing = copy.deepcopy(good)
    del missing[field]
    with pytest.raises(ValueError):
        f.validate_result(missing)
    unknown = copy.deepcopy(good)
    unknown["raw_native_exception"] = "secret"
    with pytest.raises(ValueError):
        f.validate_result(unknown)
    bad = copy.deepcopy(good)
    bad[field] = True
    with pytest.raises((ValueError, TypeError)):
        f.validate_result(bad)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("observed_at", "2026-10-20T13:00:00Z"),
        ("observed_at", "2026-10-20T13:00:00"),
        ("preview_targets", ["2026-10-20"] * 5),
        ("paper_records", -1),
        ("session_reservations", 1000001),
        ("runtime_status", "ABSENT"),
        ("f1_source_head", "c" * 40),
        ("scheduler_status", "MATCH"),
        ("child_artifact_count", 1),
    ],
)
def test_result_specific_mutations(fake, field, bad):
    result = f.preflight()
    result[field] = bad
    with pytest.raises(ValueError):
        f.validate_result(result)


@pytest.mark.parametrize("counter", f.EFFECTS)
def test_every_effect_must_be_zero(fake, counter):
    result = f.preflight()
    result["effects"][counter] = 1
    with pytest.raises(ValueError):
        f.validate_result(result)


@pytest.mark.parametrize(
    "name",
    [
        "arch134-f1-five-session-soak-v1.jsonl",
        "arch134-f1-child-test.jsonl",
        "arch134-f1-child-test.d1r7.claim",
        "arch134-f1-child-test.d1r8.claim",
        "arch134-f1-five-session-soak-v1.scheduler-create.claim",
        "arch134-f1-five-session-soak-v1.scheduler-run.claim",
        "arch134-f1-supervisor.lock",
        "arch134-f1-child.lock",
        "ARCH134-F1-unexpected",
    ],
)
@pytest.mark.parametrize("payload", [b"active", b'{"event":"FINAL"}\n', b"malformed"])
def test_namespace_blocks_existence_without_reading_or_changing(
    tmp_path, monkeypatch, name, payload
):
    monkeypatch.setattr(f, "PARENT", tmp_path)
    host = f.ReadOnlyHost()
    assert host.namespace()
    path = tmp_path / name
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        host.namespace()
    assert path.read_bytes() == payload
    assert list(tmp_path.iterdir()) == [path]


def test_directory_missing_redirection_and_non_directory(tmp_path, monkeypatch):
    host = f.ReadOnlyHost()
    with pytest.raises(FileNotFoundError):
        host.directory(tmp_path / "missing")
    path = tmp_path / "file"
    path.write_bytes(b"x")
    with pytest.raises(ValueError):
        host.directory(path)
    monkeypatch.setattr(
        f, "checked_path", lambda p: (_ for _ in ()).throw(ValueError("reparse"))
    )
    with pytest.raises(ValueError):
        host.directory(tmp_path)


@pytest.fixture
def source_host(monkeypatch):
    host = f.ReadOnlyHost()
    registry = "\n\n".join(
        "worktree " + str(p) for p in (f.MAIN, f.ROOT, *(s[1] for s in f.SOURCES))
    )
    values = {(f.MAIN, ("worktree", "list", "--porcelain")): registry}
    for _, root, branch, head, tree in f.SOURCES:
        for args, expected in (
            (("rev-parse", "--show-toplevel"), str(root)),
            (("rev-parse", "--git-common-dir"), str(f.MAIN / ".git")),
            (("branch", "--show-current"), branch),
            (("rev-parse", "HEAD"), head),
            (("rev-parse", "HEAD^{tree}"), tree),
            (("status", "--porcelain=v1", "--untracked-files=all"), ""),
            (("remote", "get-url", "origin"), f.ORIGIN),
            (("remote", "get-url", "--push", "origin"), f.ORIGIN),
            (
                ("rev-parse", "--symbolic-full-name", "@{upstream}"),
                "refs/remotes/origin/" + branch,
            ),
            (("rev-parse", "origin/" + branch), head),
            (("rev-parse", "origin/" + branch + "^{tree}"), tree),
            (
                ("ls-remote", "origin", "refs/heads/" + branch),
                head + "\trefs/heads/" + branch,
            ),
            (("worktree", "list", "--porcelain"), registry),
        ):
            values[(root, args)] = expected
    monkeypatch.setattr(host, "directory", lambda root: (1, 2))
    monkeypatch.setattr(host, "git", lambda root, *args: values[(root, args)])
    # Frozen source reads use only this new test worktree, never the real F1 tree.
    monkeypatch.setattr(
        f, "read", lambda p, *args: (ROOT / p.relative_to(f.F1_ROOT)).read_bytes()
    )
    return host, values


def test_all_frozen_sources_and_blobs(source_host):
    host, _ = source_host
    assert host.sources()
    for path, pin in f.F1_BLOBS.items():
        assert runner._git_blob_sha1(ROOT / path) == pin


@pytest.mark.parametrize("ordinal", range(3))
@pytest.mark.parametrize(
    "kind",
    [
        "branch",
        "head",
        "tree",
        "tracked",
        "staged",
        "untracked",
        "origin",
        "push",
        "upstream",
        "tracking",
        "remote",
        "registry",
        "common",
        "path",
    ],
)
def test_each_source_admission_mutation(source_host, ordinal, kind):
    host, values = source_host
    _, root, branch, _, _ = f.SOURCES[ordinal]
    args = {
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        **dict.fromkeys(
            ("tracked", "staged", "untracked"),
            ("status", "--porcelain=v1", "--untracked-files=all"),
        ),
        "origin": ("remote", "get-url", "origin"),
        "push": ("remote", "get-url", "--push", "origin"),
        "upstream": ("rev-parse", "--symbolic-full-name", "@{upstream}"),
        "tracking": ("rev-parse", "origin/" + branch),
        "remote": ("ls-remote", "origin", "refs/heads/" + branch),
        "registry": ("worktree", "list", "--porcelain"),
        "common": ("rev-parse", "--git-common-dir"),
        "path": ("rev-parse", "--show-toplevel"),
    }[kind]
    values[(root, args)] = "unexpected"
    with pytest.raises(ValueError):
        host.sources()


@pytest.mark.parametrize("relative", f.F1_BLOBS)
def test_every_frozen_blob_one_byte_drift_blocks(source_host, monkeypatch, relative):
    host, _ = source_host
    reader = f.read
    monkeypatch.setattr(
        f,
        "read",
        lambda p, *args: (
            reader(p, *args) + (b"x" if p == f.F1_ROOT / relative else b"")
        ),
    )
    with pytest.raises(ValueError):
        host.sources()


@pytest.mark.parametrize(
    "bad",
    [
        b'{"status":"MATCH"}',
        b'{"status":"CREATED"}',
        b'{"status":"STARTED"}',
        b'{"status":"BLOCKED"}',
        b"bad",
        b'{"status":"ABSENT","x":0}',
        b'{"status":"ABSENT","status":"ABSENT"}',
        b'{ "status": "ABSENT" }',
    ],
)
def test_scheduler_closed_absent_only(monkeypatch, bad):
    monkeypatch.setattr(
        f.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=bad, stderr=b""),
    )
    with pytest.raises(ValueError):
        f.ReadOnlyHost().scheduler()


@pytest.mark.parametrize("kind", ["ok", "stderr", "exit", "timeout"])
def test_scheduler_exact_transport_and_native_ambiguity(monkeypatch, kind):
    def run(argv, **kwargs):
        assert argv == [
            str(f.POWERSHELL),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(f.F1_ROOT / "scripts/arch134_f1_scheduler.ps1"),
            "-Mode",
            "Observe",
        ]
        assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["timeout"] == 45
        if kind == "timeout":
            raise subprocess.TimeoutExpired(argv, 45)
        return SimpleNamespace(
            returncode=int(kind == "exit"),
            stdout=b'{"status":"ABSENT"}\r\n',
            stderr=b"private" if kind == "stderr" else b"",
        )

    monkeypatch.setattr(f.subprocess, "run", run)
    if kind == "ok":
        f.ReadOnlyHost().scheduler()
    else:
        with pytest.raises((ValueError, subprocess.TimeoutExpired)):
            f.ReadOnlyHost().scheduler()


@pytest.fixture
def predecessors(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "PARENT", tmp_path)
    for name, payload in (("D1R5", wake_payload()), ("D1R6", arm_payload())):
        pin = getattr(f.predecessor, name)
        monkeypatch.setattr(
            f.predecessor,
            name,
            replace(pin, size=len(payload), sha256=hashlib.sha256(payload).hexdigest()),
        )
        (tmp_path / pin.basename).write_bytes(payload)
    return tmp_path


def test_predecessors_bounded_public_binder(predecessors):
    host = f.ReadOnlyHost()
    assert host.predecessors()
    assert host.observations["predecessor_reads"] == 2


@pytest.mark.parametrize("which", ["D1R5", "D1R6"])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "bytes",
        "schema",
        "source",
        "session",
        "final",
        "unreadable",
        "reparse",
    ],
)
def test_predecessor_failures(predecessors, monkeypatch, which, mutation):
    pin = getattr(f.predecessor, which)
    path = predecessors / pin.basename
    if mutation == "missing":
        path.unlink()
    elif mutation in {"unreadable", "reparse"}:

        def rejected(*args):
            raise OSError("private")

        monkeypatch.setattr(f.predecessor, "read_evidence", rejected)
    else:
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        if mutation == "bytes":
            data = path.read_bytes() + b"x"
        else:
            for row in rows:
                facts = row if which == "D1R5" else row["facts"]
                if mutation == "schema":
                    row["schema"] = "unknown/v1"
                elif mutation == "source":
                    facts["source_head"] = "a" * 40
                elif mutation == "session":
                    facts["target_session"] = "2026-10-15"
                elif row["event"] == "FINAL":
                    row["classification"] = "BLOCKED"
            data = b"".join(f.predecessor.canonical(r) + b"\n" for r in rows)
            monkeypatch.setattr(
                f.predecessor,
                which,
                replace(pin, size=len(data), sha256=hashlib.sha256(data).hexdigest()),
            )
        path.write_bytes(data)
    before = {p.name: p.read_bytes() for p in predecessors.iterdir()}
    with pytest.raises((OSError, ValueError, KeyError)):
        f.ReadOnlyHost().predecessors()
    assert {p.name: p.read_bytes() for p in predecessors.iterdir()} == before


def runtime_result():
    return dict(
        schema="production-paper-runtime-preflight/v1",
        status="PRESENT_COMPATIBLE",
        paper_records=3,
        session_reservations=4,
        paper_store_write_readiness="NOT_CHECKED",
        session_store_write_readiness="NOT_CHECKED",
        **dict.fromkeys(
            (
                "alpaca_credential_reads",
                "robinhood_credential_reads",
                "alpaca_http_calls",
                "robinhood_application_calls",
                "paper_trade_mutations",
                "runtime_writes",
                "scheduler_mutations",
                "broker_mutations",
            ),
            0,
        ),
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("status", "ABSENT"),
        ("status", "BLOCKED"),
        ("status", "UNKNOWN"),
        ("paper_records", True),
        ("paper_records", -1),
        ("session_reservations", 1000001),
        ("runtime_writes", 1),
        ("alpaca_credential_reads", 1),
        ("paper_store_write_readiness", "PASS"),
    ],
)
def test_runtime_fail_closed(monkeypatch, field, bad):
    value = runtime_result()
    value[field] = bad
    monkeypatch.setattr(f, "preflight_runtime", lambda: value)
    with pytest.raises(ValueError):
        f.ReadOnlyHost().runtime()


def test_runtime_read_only_counts_and_fingerprint(tmp_path, monkeypatch):
    paths = []
    monkeypatch.setattr(f, "preflight_runtime", runtime_result)
    for name in ("paper.sqlite", "armed-sessions.sqlite"):
        (tmp_path / name).write_bytes(b"disposable fingerprint")

    # Redirect only the fixed data paths, keeping all reads disposable.
    def reader(path, limit):
        paths.append((path.name, limit))
        return (tmp_path / path.name).read_bytes()

    monkeypatch.setattr(f, "read", reader)
    original = f.Path
    monkeypatch.setattr(
        f,
        "Path",
        lambda value: (
            tmp_path if str(value) == r"F:\AITradingBot\Arch134D1" else original(value)
        ),
    )
    counts, snapshots = f.ReadOnlyHost().runtime()
    assert counts == (3, 4) and len(snapshots) == 2
    assert paths == [("paper.sqlite", 134217728), ("armed-sessions.sqlite", 134217728)]


def test_capability_ast_and_frozen_source_no_mutation():
    tree = ast.parse(
        (
            ROOT / "src/trading_bot/review_paper/five_session_soak_readiness.py"
        ).read_text()
    )
    forbidden = {
        "authorize",
        "supervise",
        "reserve",
        "exclusive",
        "lock",
        "publish_prerequisite",
        "run_session",
        "qualify_runtime_write_readiness",
        "provision_runtime",
        "connect",
        "write_bytes",
        "write_text",
        "unlink",
        "mkdir",
        "Popen",
    }
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    for node in calls:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "append":
            assert isinstance(node.func.value, ast.Name)
            assert node.func.value.id in {"snapshots", "payloads", "identities"}
    assert (
        not {n.func.attr for n in calls if isinstance(n.func, ast.Attribute)}
        & forbidden
    )
    assert not {n.func.id for n in calls if isinstance(n.func, ast.Name)} & forbidden
    mutating_git = {
        "fetch",
        "pull",
        "checkout",
        "switch",
        "reset",
        "merge",
        "rebase",
        "clean",
        "add",
        "commit",
        "push",
        "branch",
        "update-ref",
    }
    for node in calls:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "git"
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
        ):
            verb = node.args[1].value
            assert verb not in mutating_git or (
                verb == "branch" and node.args[2].value == "--show-current"
            )
    assert len(f.F1_BLOBS) == 7


def test_registration_source_only_verification_and_ci_route():
    spec = runner._checkpoint_specs()[runner.ARCH134_F2_NAME]
    assert spec.preflight is runner._arch134_f2_preflight and spec.execute is None
    assert spec.remote_branch == f.BRANCH and spec.remote_head_env is None
    assert runner.ACTIVE_CI_CHECKPOINTS.count(spec.name) == 1
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), f.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner._checkpoint_specs()[runner.ARCH134_F1_NAME].preflight is None
    assert runner._checkpoint_specs()[runner.ARCH134_F1_NAME].execute is None
    assert runner._arch134_f2_authority_check(ROOT) == ()


@pytest.mark.parametrize("kind", ["exception", "unknown_field", "missing_field"])
def test_runtime_exception_or_shape_blocks(fake, monkeypatch, kind):
    def inspection():
        if kind == "exception":
            raise OSError("native private account data")
        value = runtime_result()
        if kind == "unknown_field":
            value["raw"] = "secret"
        else:
            del value["runtime_writes"]
        return value

    monkeypatch.setattr(f, "preflight_runtime", inspection)
    # Bind the actual read-only edge to the fake orchestrator.
    fake.runtime = lambda: f_readonly_runtime(fake)
    result = f.preflight()
    assert result["status"] == "BLOCKED"
    f.validate_result(result)
    assert "secret" not in json.dumps(result) and "native private" not in json.dumps(
        result
    )


# Save the production method before any fixture replaces the class constructor.
f_readonly_runtime = f.ReadOnlyHost.runtime
f_readonly_namespace = f.ReadOnlyHost.namespace


@pytest.mark.parametrize(
    "name",
    [
        "arch134-f1-five-session-soak-v1.jsonl",
        "arch134-f1-child-new.jsonl",
        "arch134-f1-child-new.d1r7.claim",
        "arch134-f1-child-new.d1r8.claim",
        "arch134-f1-five-session-soak-v1.scheduler-run.claim",
        "arch134-f1-child.lock",
    ],
)
def test_artifact_appears_during_final_readmission(fake, tmp_path, monkeypatch, name):
    monkeypatch.setattr(f, "PARENT", tmp_path)
    fake.directory = lambda path: (1, 2)
    count = []

    def namespace():
        count.append(1)
        if len(count) == 2:
            (tmp_path / name).write_bytes(b"simulated concurrent writer")
        return f_readonly_namespace(fake)

    fake.namespace = namespace
    assert f.preflight()["status"] == "BLOCKED"
    assert (tmp_path / name).read_bytes() == b"simulated concurrent writer"


@pytest.mark.parametrize(
    "field", ["directory", "source", "runtime", "scheduler", "predecessors"]
)
def test_first_observation_exception_is_sanitized(fake, field):
    def rejected(*args):
        raise OSError("private S-1-5-21 provider account token")

    setattr(fake, "f2_source" if field in {"directory", "source"} else field, rejected)
    result = f.preflight()
    f.validate_result(result)
    assert result["status"] == "BLOCKED" and "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "kind",
    ["success", "dirty", "remote", "local_drift", "invalid_result", "evidence_inside"],
)
def test_runner_preflight_admission_and_ready_enum(fake, tmp_path, monkeypatch, kind):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(f, "ROOT", repo)
    monkeypatch.setattr(f, "PARENT", tmp_path / "qualification")
    monkeypatch.setattr(runner, "_arch134_f2_authority_check", lambda root: ())
    result = f.preflight()
    if kind == "invalid_result":
        result["raw_native_exception"] = "private"
    monkeypatch.setattr(runner, "_arch134_f2_preflight", lambda: result)
    spec = runner._checkpoint_specs()[runner.ARCH134_F2_NAME]
    states = []

    def state(root):
        states.append(1)
        return dict(
            head="c" * 40 if kind == "local_drift" and len(states) > 1 else "a" * 40,
            tree="b" * 40,
            branch=f.BRANCH,
            porcelain="?? occupied" if kind == "dirty" else "",
        )

    monkeypatch.setattr(runner, "_git_state", state)
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda *args: "c" * 40 if kind == "remote" else "a" * 40,
    )
    monkeypatch.setattr(runner, "_git_output", lambda *args: "worktree " + str(repo))
    evidence = repo / "evidence" if kind == "evidence_inside" else tmp_path / "evidence"
    if kind in {"dirty", "remote", "invalid_result", "evidence_inside"}:
        with pytest.raises(RuntimeError):
            runner.preflight_checkpoint(spec, repo_root=repo, evidence_root=evidence)
    else:
        passed, report = runner.preflight_checkpoint(
            spec, repo_root=repo, evidence_root=evidence
        )
        assert passed == (kind == "success")
        assert json.loads(report.read_text())["result"]["status"] == f.READY


@pytest.mark.parametrize(
    "kind", ["missing", "extra", "predecessor", "digest", "registration"]
)
def test_f2_metadata_and_registration_fail_closed(monkeypatch, kind):
    if kind == "registration":
        profiles = dict(runner.CI_CERTIFICATION_PROFILES)
        profiles[runner.ARCH134_F2_NAME] = "full"
        monkeypatch.setattr(runner, "CI_CERTIFICATION_PROFILES", profiles)
        assert runner._arch134_f2_authority_check(ROOT)
        return
    path = "tests/runtime/checkpoint_runner/test_ci.py"
    pins = dict(runner.ARCH134_F2_PIN_OVERRIDES)
    before = runner.ARCH134_F2_PREDECESSOR_PINS[path]
    if kind == "missing":
        pins.pop(path)
    elif kind == "extra":
        pins["src/forbidden.py"] = "a" * 40
    elif kind == "predecessor":
        before = "c" * 40
    else:
        monkeypatch.setattr(runner, "ARCH134_F2_PINS_SHA256", "f" * 64)
    monkeypatch.setattr(runner, "ARCH134_F2_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch134_f2_current_pin(path, before)


def test_contract_pins_and_effect_inventory_match_frozen_design():
    design = (
        ROOT / "docs/architecture/134-f2-five-session-live-paper-soak-readiness.md"
    ).read_text(encoding="utf-8")
    assert set(re.findall(r"^([A-Z0-9_]+)=0$", design, re.MULTILINE)) == set(f.EFFECTS)
    for _, _, branch, head, tree in f.SOURCES:
        assert len(head) == len(tree) == 40
        assert head in design and tree in design
        assert branch.startswith("feature/robinhood-")
    for path, blob in f.F1_BLOBS.items():
        assert path + "\n" + blob in design


def test_f2_only_dispatch_additions_preserve_frozen_predecessor_ast():
    tree = ast.parse(
        (ROOT / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    )
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "preflight_checkpoint"
    )
    current = hashlib.sha256(
        ast.dump(function, include_attributes=False).encode()
    ).hexdigest()
    assert runner.SUPERVISED_INSTALLATION_RUNNER_PINS[function.name] == current
    predecessor_pin = "a5e63c447cb53e2998b4234dc0ecb2f81c2954b7677bc78d8414f6d278b8b15f"
    assert runner.SUPERVISED_PUBLICATION_RUNNER_PINS[function.name] == predecessor_pin
    predecessor = copy.deepcopy(function)
    predicate = ast.dump(ast.parse("spec.name == ARCH134_F2_NAME", mode="eval").body)
    branches = [
        node
        for node in predecessor.body
        if isinstance(node, ast.If) and ast.dump(node.test) == predicate
    ]
    assert len(branches) == 2
    assert not branches[0].orelse
    assert len(branches[1].orelse) == 1 and isinstance(
        branches[1].orelse[0], ast.Assign
    )
    predecessor.body = [
        part
        for node in predecessor.body
        for part in (node.orelse if node in branches else [node])
    ]
    assert (
        hashlib.sha256(
            ast.dump(predecessor, include_attributes=False).encode()
        ).hexdigest()
        == predecessor_pin
    )


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "branch",
        "dirty",
        "origin",
        "push",
        "remote",
        "head",
        "tree",
        "interpreter",
        "platform",
        "file",
    ],
)
def test_f2_own_fixed_host_admission(monkeypatch, mutation):
    host = f.ReadOnlyHost()
    monkeypatch.setattr(host, "directory", lambda path: (1, 2))
    monkeypatch.setattr(
        f, "os", SimpleNamespace(name="posix" if mutation == "platform" else "nt")
    )
    monkeypatch.setattr(
        f,
        "sys",
        SimpleNamespace(
            executable=str(f.MAIN if mutation == "interpreter" else f.PYTHON)
        ),
    )
    monkeypatch.setattr(
        f,
        "__file__",
        str(
            (f.MAIN if mutation == "file" else f.ROOT)
            / "src/trading_bot/review_paper/five_session_soak_readiness.py"
        ),
    )
    values = {
        ("branch", "--show-current"): f.BRANCH,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("remote", "get-url", "origin"): f.ORIGIN,
        ("remote", "get-url", "--push", "origin"): f.ORIGIN,
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
        ("ls-remote", "origin", "refs/heads/" + f.BRANCH): "a" * 40
        + "\trefs/heads/"
        + f.BRANCH,
    }
    keys = dict(
        branch=("branch", "--show-current"),
        dirty=("status", "--porcelain=v1", "--untracked-files=all"),
        origin=("remote", "get-url", "origin"),
        push=("remote", "get-url", "--push", "origin"),
        remote=("ls-remote", "origin", "refs/heads/" + f.BRANCH),
        head=("rev-parse", "HEAD"),
        tree=("rev-parse", "HEAD^{tree}"),
    )
    if mutation in keys:
        values[keys[mutation]] = "unexpected"
    monkeypatch.setattr(host, "git", lambda root, *args: values[args])
    if mutation is None:
        assert host.f2_source() == ("a" * 40, "b" * 40)
    else:
        with pytest.raises(ValueError):
            host.f2_source()


@pytest.mark.parametrize("kind", ["ok", "stderr", "exit", "oversized", "timeout"])
def test_git_transport_is_read_only_and_bounded(monkeypatch, kind):
    def run(argv, **kwargs):
        assert argv == [
            "git",
            "--no-optional-locks",
            "-C",
            str(f.F1_ROOT),
            "rev-parse",
            "HEAD",
        ]
        assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["timeout"] == 30
        if kind == "timeout":
            raise subprocess.TimeoutExpired(argv, 30)
        return SimpleNamespace(
            returncode=int(kind == "exit"),
            stderr=b"private" if kind == "stderr" else b"",
            stdout=b"x" * 262145 if kind == "oversized" else b"a" * 40,
        )

    monkeypatch.setattr(f.subprocess, "run", run)
    if kind == "ok":
        assert f.ReadOnlyHost().git(f.F1_ROOT, "rev-parse", "HEAD") == "a" * 40
    else:
        with pytest.raises((ValueError, subprocess.TimeoutExpired)):
            f.ReadOnlyHost().git(f.F1_ROOT, "rev-parse", "HEAD")
