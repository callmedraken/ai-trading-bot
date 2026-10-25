"""Disposable-only D1S1 source contract, ordering and publication integration."""

import ast
import json
import socket
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
import test_supervised_runtime_host_admission as production_fixtures

from trading_bot.review_paper import successor_soak as controller
from trading_bot.review_paper import successor_soak_admission as admission
from trading_bot.review_paper import successor_soak_contract as contract
from trading_bot.review_paper import successor_soak_store as store
from trading_bot.supervised_release.runtime_isolation import InstalledRuntimeMaterial

production_setup = production_fixtures.setup

ROOT = Path(__file__).resolve().parents[2]
BASE = "a5485a64dd9848e74daf9596bbb3194dc458e363"
SOURCE_PATHS = tuple(
    "src/trading_bot/review_paper/" + name + ".py"
    for name in (
        "successor_soak",
        "successor_soak_admission",
        "successor_soak_contract",
        "successor_soak_store",
    )
)


class Observations:
    def __init__(self):
        self.store = admission.StoreObservation(
            contract.PRODUCTION_ROOT,
            contract.PRODUCTION_ROOT,
            r"F:\AITradingBot\Arch133",
            True,
            True,
            True,
            True,
            (7, 900),
        )
        self.process = admission.ManualProcessObservation(
            100, "windows-filetime:1000", contract.SESSIONS[0]
        )
        self.calls = []

    def observe_store(self):
        self.calls.append("store")
        return self.store

    def observe_manual_process(self):
        self.calls.append("process")
        return self.process


@pytest.fixture
def harness(production_setup, tmp_path, monkeypatch):
    # Native production observation is replaced by the retained 133 fake fixture.
    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **k: pytest.fail("network entry")
    )
    observations = Observations()
    f = production_setup
    boundary = admission.ManualStartBoundary(
        f.release, f.binding, f.installed, f.native, f.runtime, observations
    )
    data = store.DisposableSuccessorStorage(tmp_path)
    subject = controller.SuccessorController(boundary, data)
    return SimpleNamespace(
        source=f,
        observations=observations,
        boundary=boundary,
        storage=data,
        subject=subject,
        lineage=boundary.admit().lineage,
        root=tmp_path,
    )


def start(
    h,
    disposition=contract.QuoteDisposition.NO_SIGNAL,
    *,
    quote=None,
    paper=None,
    guard=None,
):
    return h.subject.manual_start(
        quote_seam=quote or (lambda: disposition),
        paper_seam=paper or (lambda: True),
        pre_entry_guard=guard or (lambda: True),
    )


def second_process(h, *, target=None):
    h.observations.process = admission.ManualProcessObservation(
        101, "windows-filetime:1001", target or contract.SESSIONS[1]
    )


def fail():
    raise RuntimeError("unserializable secret/provider/exception body")


def test_frozen_semantics_and_closed_signature(harness):
    assert contract.DESIGN_SCHEMA == "arch134-f1r1-d1-successor-soak-design/v1"
    assert contract.LINEAGE_SCHEMA == "arch134-f1r1-d1-successor-lineage/v1"
    assert contract.EVIDENCE_SCHEMA == "arch134-f1r1-d1-successor-evidence/v1"
    assert contract.IDENTITY_NAMESPACE == "arch134-f1r1-d1-successor-soak-identity/v1"
    assert (
        contract.PRODUCTION_ROOT
        == r"F:\AITradingBot\Arch133\arch134-f1r1-d1-successor-soak-v1"
    )
    assert store.NAMES == (
        "successor-parent-v1.jsonl",
        "successor-session-01-v1.jsonl",
        "successor-session-02-v1.jsonl",
    )
    assert contract.SESSIONS == ("2026-11-02", "2026-11-03")
    assert contract.PRODUCT == ("SPY", "LONG_ONLY", "US_ETF", "SYNTHETIC_REVIEW_PAPER")
    with pytest.raises(TypeError):
        harness.subject.manual_start(symbol="QQQ")
    for ordinal in (0, 3, 5, True, "1"):
        with pytest.raises(ValueError):
            harness.lineage.child_id(ordinal)


def test_uuid5_material_and_nondeterministic_metadata_excluded(harness):
    lineage = harness.lineage
    assert UUID(lineage.parent_id).version == 5
    assert UUID(lineage.child_id(1)).version == 5
    assert len({lineage.parent_id, lineage.child_id(1), lineage.child_id(2)}) == 3
    assert contract.SuccessorLineage.from_facts(lineage.facts()) == lineage
    second_process(harness)
    harness.observations.store = replace(harness.observations.store, identity=(9, 999))
    assert harness.boundary.admit().lineage.parent_id == lineage.parent_id
    material = replace(lineage.material, binding_sha256="d" * 64)
    assert contract.SuccessorLineage(material).parent_id != lineage.parent_id
    for key in (
        "pid",
        "birth",
        "clock",
        "path",
        "journal",
        "scheduler",
        "random",
        "token",
    ):
        changed = lineage.facts() | {key: "forbidden"}
        with pytest.raises(ValueError):
            contract.SuccessorLineage.from_facts(changed)
    with pytest.raises(ValueError):
        contract.SuccessorLineage(
            InstalledRuntimeMaterial(
                lineage.material.manifest, lineage.material.binding_sha256
            )
        )


@pytest.mark.parametrize(
    "disposition,terminal",
    [
        (contract.QuoteDisposition.NO_SIGNAL, contract.SessionTerminal.NO_SIGNAL),
        (
            contract.QuoteDisposition.RISK_REJECTED,
            contract.SessionTerminal.RISK_REJECTED,
        ),
        (
            contract.QuoteDisposition.PAPER_REQUIRED,
            contract.SessionTerminal.PAPER_EXECUTED,
        ),
    ],
)
def test_exact_two_session_progression_and_terminal_read_only(
    harness, disposition, terminal
):
    assert start(harness, disposition) is terminal
    first = controller.snapshot(harness.storage, harness.lineage)
    assert first.terminal is None and len(first.children) == 1
    second_process(harness)
    assert start(harness, disposition) is terminal
    state = controller.snapshot(harness.storage, harness.lineage)
    assert state.terminal == "SERIES_COMPLETED"
    assert len(state.children) == 2
    before = {name: harness.storage.read(name) for name in store.NAMES}
    assert start(harness, quote=fail, paper=fail) == "SERIES_COMPLETED"
    assert {name: harness.storage.read(name) for name in store.NAMES} == before
    assert (
        state.counters["manual_start_admissions"]
        == state.counters["prerequisite_admissions"]
        == state.counters["prerequisite_publications"]
        == 2
    )
    assert (
        state.counters["provider_entries"] == state.counters["credential_phases"] == 2
    )
    assert state.counters["paper_fills"] == (
        2 if disposition is contract.QuoteDisposition.PAPER_REQUIRED else 0
    )
    assert [row["event"] for row in state.parent.rows] == [
        "PARENT_RESERVED",
        "SOURCE_ADMITTED",
        "RUNTIME_HOST_ADMITTED",
        "SESSION_TUPLE_BOUND",
        "SESSION_01_GRANT_INTENT",
        "SESSION_01_FINAL",
        "SESSION_02_GRANT_INTENT",
        "SESSION_02_FINAL",
        "SERIES_COMPLETED",
    ]


def test_effect_entry_and_ack_order_with_durable_readback(harness):
    calls = []

    def quote():
        replay = store.SuccessorJournal(harness.storage, harness.lineage, 1).read()
        assert replay.rows[-1]["data"]["stage"] == "ENTRY_ADMITTED"
        assert [
            r["data"]["stage"] for r in replay.rows if r["event"] == "QUOTE_EFFECT"
        ] == ["INTENT", "ENTRY_ADMITTED"]
        calls.append("quote")
        return contract.QuoteDisposition.PAPER_REQUIRED

    def paper():
        replay = store.SuccessorJournal(harness.storage, harness.lineage, 1).read()
        assert replay.rows[-1]["data"]["stage"] == "ENTRY_ADMITTED"
        assert [
            r["data"]["stage"] for r in replay.rows if r["event"] == "QUOTE_EFFECT"
        ][-1] == "ACK"
        calls.append("paper")
        return True

    assert (
        start(harness, quote=quote, paper=paper)
        is contract.SessionTerminal.PAPER_EXECUTED
    )
    assert calls == ["quote", "paper"]


@pytest.mark.parametrize(
    "failure", ["guard", "quote", "paper", "invalid_quote", "invalid_paper"]
)
def test_halting_matrix_consumes_entry_and_never_retries(harness, failure):
    kwargs = {
        "guard": {"guard": lambda: False, "quote": fail},
        "quote": {"quote": fail},
        "paper": {
            "disposition": contract.QuoteDisposition.PAPER_REQUIRED,
            "paper": fail,
        },
        "invalid_quote": {"quote": lambda: "NO_SIGNAL"},
        "invalid_paper": {
            "disposition": contract.QuoteDisposition.PAPER_REQUIRED,
            "paper": lambda: None,
        },
    }[failure]
    expected = (
        contract.SessionTerminal.BLOCKED
        if failure == "guard"
        else contract.SessionTerminal.INDETERMINATE
    )
    assert start(harness, **kwargs) is expected
    state = controller.snapshot(harness.storage, harness.lineage)
    assert state.terminal == "SERIES_HALTED"
    raw = b"".join(harness.storage.read(name) or b"" for name in store.NAMES)
    assert b"unserializable" not in raw
    assert b"secret/provider" not in raw
    assert state.counters["provider_entries"] == (0 if failure == "guard" else 1)
    assert state.counters["paper_attempts"] == (0 if failure == "guard" else 1)
    assert state.counters["paper_fills"] == (
        1 if failure in {"paper", "invalid_paper"} else 0
    )
    assert start(harness, quote=fail, paper=fail) == "SERIES_HALTED"
    assert b"".join(harness.storage.read(name) or b"" for name in store.NAMES) == raw


@pytest.mark.parametrize("observed", ["2026-11-03", "2026-11-04", "2027-01-01"])
def test_missed_session_halts_without_backfill(harness, observed):
    harness.observations.process = replace(
        harness.observations.process, observed_date=observed
    )
    assert (
        start(harness, quote=fail, paper=fail)
        is contract.SessionTerminal.SESSION_MISSED
    )
    state = controller.snapshot(harness.storage, harness.lineage)
    assert state.terminal == "SERIES_HALTED"
    assert state.children[0].header["target_session"] == "2026-11-02"
    assert (
        state.counters["provider_entries"]
        == state.counters["prerequisite_publications"]
        == 0
    )


def test_early_start_has_no_reservation(harness):
    harness.observations.process = replace(
        harness.observations.process, observed_date="2026-11-01"
    )
    with pytest.raises(ValueError):
        start(harness)
    assert not list(harness.root.iterdir())


def test_duplicate_parent_and_same_process_second_start_rejected(harness):
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    parent = store.SuccessorJournal(harness.storage, harness.lineage)
    with pytest.raises((ValueError, FileExistsError)):
        parent.reserve(parent.read().header, "PARENT_RESERVED")
    harness.observations.process = replace(
        harness.observations.process, observed_date=contract.SESSIONS[1]
    )
    with pytest.raises(ValueError):
        start(harness)
    assert harness.storage.read(contract.SESSION_NAMES[1]) is None


@pytest.mark.parametrize("cut", ["INTENT", "ENTRY_ADMITTED", "ACK", "SESSION_FINAL"])
def test_failed_durability_preserves_consumed_prefix_and_no_seam_retry(
    harness, monkeypatch, cut
):
    original = harness.storage.append
    calls = []

    def append(name, expected, data):
        row = json.loads(data)
        if row["event"] == cut or row["data"].get("stage") == cut:
            raise OSError("bounded fake write failure")
        original(name, expected, data)

    monkeypatch.setattr(harness.storage, "append", append)
    assert (
        start(
            harness,
            quote=lambda: calls.append(1) or contract.QuoteDisposition.NO_SIGNAL,
        )
        is contract.SessionTerminal.INDETERMINATE
    )
    before = {n: harness.storage.read(n) for n in store.NAMES}
    with pytest.raises(ValueError):
        start(harness, quote=fail)
    assert {n: harness.storage.read(n) for n in store.NAMES} == before
    assert len(calls) == (1 if cut in {"ACK", "SESSION_FINAL"} else 0)


@pytest.mark.parametrize(
    "mutation",
    [
        "partial",
        "noncanonical",
        "foreign",
        "extra",
        "sequence",
        "runtime",
        "terminal_extension",
        "over_budget",
        "duplicate_key",
    ],
)
def test_canonical_replay_and_mutation_rejection(harness, mutation):
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    second_process(harness)
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    name = contract.PARENT_NAME
    payload = harness.storage.read(name)
    rows = [json.loads(line) for line in payload.splitlines()]
    if mutation == "partial":
        damaged = payload[:-1]
    elif mutation == "noncanonical":
        damaged = b" " + payload
    elif mutation == "foreign":
        rows[0]["schema"] = "arch134-f1-five-session-soak/v1"
    elif mutation == "extra":
        rows[0]["token"] = "forbidden"
    elif mutation == "sequence":
        rows[1]["sequence"] = True
    elif mutation == "runtime":
        rows[-1]["runtime_id"] = "qualification-" + "a" * 64
    elif mutation == "terminal_extension":
        rows.append(rows[-1] | {"sequence": rows[-1]["sequence"] + 1})
    elif mutation == "over_budget":
        damaged = payload + b" " * contract.MAX_BYTES
    else:
        damaged = payload.replace(
            b'"kind":"PARENT"', b'"kind":"PARENT","kind":"PARENT"'
        )
    if mutation in {"foreign", "extra", "sequence", "runtime", "terminal_extension"}:
        damaged = b"".join(contract.canonical(row) + b"\n" for row in rows)
    with pytest.raises(ValueError):
        store.replay(damaged, harness.lineage, None)


@pytest.mark.parametrize("name,total,per_date", contract.EFFECT_CEILINGS)
def test_every_effect_ceiling_and_closed_zero_counter(name, total, per_date):
    for child, maximum in ((False, total), (True, per_date)):
        counts = contract.zero_counters()
        counts[name] = maximum
        assert contract.validate_counters(counts, session=child) == counts
        for invalid in (maximum + 1, -1, True, 1.0):
            counts[name] = invalid
            with pytest.raises(ValueError):
                contract.validate_counters(counts, session=child)


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot\Arch133\old-f1",
        contract.PRODUCTION_ROOT,
        r"F:\AI\worktrees\mutable",
        r"F:\AI\ai-trading-bot",
        r"F:\AI\temp\qualification\arch134-f1r1-host-isolation",
    ],
)
def test_protected_paths_rejected_before_any_access(path, monkeypatch):
    monkeypatch.setattr(
        Path, "lstat", lambda *a: pytest.fail("protected filesystem access")
    )
    with pytest.raises(ValueError):
        store.DisposableSuccessorStorage(Path(path))


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AI\ai-trading-bot",
        r"F:\AI\worktrees\other",
        r"F:\AI\temp\qualification\arch134-f1r1-host-isolation",
    ],
)
def test_development_or_qualification_cannot_satisfy_runtime_admission(harness, path):
    harness.source.runtime.process = replace(
        harness.source.runtime.process, working_directory=path
    )
    with pytest.raises(ValueError):
        start(harness, quote=fail)
    assert not list(harness.root.iterdir())


@pytest.mark.parametrize(
    "field,value",
    [
        ("no_reparse", False),
        ("no_aliases", False),
        ("stable", False),
        ("local_ntfs", False),
        ("path", r"F:\AI\temp\qualification\arch134-f1r1-host-isolation"),
        ("final_path", r"F:\AI\worktrees\alias"),
    ],
)
def test_successor_store_requires_exact_fresh_production_admission(
    harness, field, value
):
    harness.observations.store = replace(harness.observations.store, **{field: value})
    with pytest.raises(ValueError):
        start(harness, quote=fail)
    assert not list(harness.root.iterdir())


def test_admission_order_and_no_cached_host_replay(harness, monkeypatch):
    events = []
    for name in (
        "verify_release_bundle",
        "admit_runtime_host",
        "bind_architecture133_host",
        "admit_installed_runtime",
        "assess_host_qualification_readiness",
    ):
        original = getattr(admission, name)

        def wrapper(*args, _name=name, _original=original, **kwargs):
            events.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(admission, name, wrapper)
    harness.boundary.admit()
    assert events == [
        "verify_release_bundle",
        "admit_runtime_host",
        "bind_architecture133_host",
        "admit_installed_runtime",
        "assess_host_qualification_readiness",
    ]
    reads = harness.source.runtime.process_reads
    harness.boundary.admit()
    assert harness.source.runtime.process_reads > reads
    harness.source.runtime.process = replace(
        harness.source.runtime.process, isolated=False
    )
    with pytest.raises(ValueError):
        harness.boundary.admit()


def test_source_imports_have_no_operational_capabilities_or_resume_entry():
    for relative in SOURCE_PATHS:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports |= {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        }
        assert not imports & {
            "subprocess",
            "socket",
            "requests",
            "sqlite3",
            "win32com",
            "ctypes",
        }
        assert not any(
            i
            and any(
                part in i
                for part in (
                    "five_session_soak",
                    "d1_session",
                    "qualification",
                    "credentials",
                    "broker",
                    "scheduler",
                    "arch134_f1_bridge",
                )
            )
            for i in imports
        )
        assert not any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name in {"resume", "retry", "repair", "reset", "execute_live", "main"}
            for n in ast.walk(tree)
        )
    assert not list((ROOT / "scripts").glob("*successor*soak*"))


def test_production_and_historical_f1_source_remains_frozen():
    paths = [
        "src/trading_bot/supervised_release/" + name + ".py"
        for name in (
            "model",
            "binding",
            "bundle",
            "runtime_admission",
            "installation_contract",
            "runtime_host_composition",
            "runtime_isolation",
            "lifecycle_store",
        )
    ]
    paths += [
        "src/trading_bot/review_paper/" + name + ".py"
        for name in (
            "five_session_soak",
            "five_session_soak_store",
            "five_session_soak_child",
            "five_session_soak_host",
        )
    ]
    for path in paths:
        expected = subprocess.run(
            ["git", "show", BASE + ":" + path],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        assert (ROOT / path).read_text(encoding="utf-8").encode() == expected, path


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "wrong_before", "wrong_after"]
)
def test_exact_c1_document_overlay_fails_closed(monkeypatch, mutation):
    from scripts import checkpoint_runner as runner

    path = "docs/PROJECT_STATUS.md"
    before = runner.ARCH134_D1S1_PREDECESSOR_PINS
    assert before[path] == "2518ad685ec0501c42720e210049de70987b8387"
    assert (
        before["docs/AI_TRADING_BOT_HANDOFF.md"]
        == "c558eb4170e271cdf10be2b232ea447be3a89578"
    )
    assert (
        runner._arch134_d1s1_current_source_pin(path, before[path])
        == runner.ARCH134_D1S1_SUCCESSOR_PINS[path]
    )
    which = (
        "ARCH134_D1S1_PREDECESSOR_PINS"
        if mutation == "wrong_before"
        else "ARCH134_D1S1_SUCCESSOR_PINS"
    )
    altered = dict(getattr(runner, which))
    if mutation == "missing":
        altered.pop(path)
    elif mutation == "extra":
        altered["unreviewed"] = "a" * 40
    else:
        altered[path] = "a" * 40
    monkeypatch.setattr(runner, which, altered)
    with pytest.raises(ValueError):
        runner._arch134_d1s1_current_source_pin(path, before[path])


def test_removing_overlay_restores_c1_and_wrong_predecessor_rejected(monkeypatch):
    from scripts import checkpoint_runner as runner

    before = runner.ARCH134_D1S1_PREDECESSOR_PINS
    path = "docs/AI_TRADING_BOT_HANDOFF.md"
    with pytest.raises(ValueError):
        runner._arch134_d1s1_current_source_pin(path, "a" * 40)
    monkeypatch.setattr(runner, "ARCH134_D1S1_SUCCESSOR_PINS", None)
    for path, pin in before.items():
        assert runner._arch134_d1s1_current_source_pin(path, pin) == pin
    assert runner._arch134_d1s1_current_source_pin("unrelated", "b" * 40) == "b" * 40


def test_checkpoint_profile_and_exact_authority_consumers():
    from scripts import checkpoint_runner as runner

    spec = runner._checkpoint_specs()[runner.ARCH134_D1S1_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner._arch134_d1s2_active_inventory() == runner.ACTIVE_CI_CHECKPOINTS[1:]
    assert runner._arch134_d1s1_authority_check(ROOT) == ()


def test_frozen_predecessor_dictionaries_and_runner_ast_overlay():
    from scripts import checkpoint_runner as runner

    before = subprocess.run(
        ["git", "show", BASE + ":scripts/checkpoint_runner.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    after = (ROOT / "scripts/checkpoint_runner.py").read_text()
    old = {
        n.target.id: n.value
        for n in ast.parse(before).body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    current = {
        n.target.id: n.value
        for n in ast.parse(after).body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    for name in old:
        if name not in {
            "ACTIVE_CI_CHECKPOINTS",
            "REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256",
            "CI_CERTIFICATION_PROFILES",
        }:
            assert ast.dump(old[name]) == ast.dump(current[name]), name
    functions = {
        n.name: n for n in ast.parse(before).body if isinstance(n, ast.FunctionDef)
    }
    new_functions = {
        n.name: n for n in ast.parse(after).body if isinstance(n, ast.FunctionDef)
    }
    changed = {
        name
        for name, node in functions.items()
        if ast.dump(node) != ast.dump(new_functions[name])
    }
    changed.discard("_batch_workflow_is_reviewed")
    assert changed == (
        set(runner.ARCH134_D1S1_PREDECESSOR_AST_PINS)
        | set(runner.ARCH134_D1S2_PREDECESSOR_AST_PINS)
        | (set(runner.ARCH132_R3M_C3_AST_PREDECESSORS) & changed)
        | (
            set(runner.ARCH134_D1S3_RUNNER_AST_PINS)
            - {
                "_arch134_d1s3_preflight",
                "_arch134_d1s3_execute",
                "_arch134_d1s3_authority_check",
                "_arch134_d1s2_current_source_pin",
                "_arch134_d1s2_active_inventory",
                "_arch134_d1s2_authority_check",
                "_arch134_d1s2_source_pin",
                "_arch134_d1s3_mutable_current_doc",
                "_arch134_d1s3_shared_successor_pin",
            }
        )
    ) - {"_arch134_d1s1_authority_check"}
    for name, pin in runner.ARCH134_D1S1_PREDECESSOR_AST_PINS.items():
        if name in runner.ARCH134_D1S2_PREDECESSOR_AST_PINS:
            continue
        assert (
            runner._arch134_d1s1_runner_ast_pin(name, pin)
            == runner.ARCH134_D1S1_SUCCESSOR_AST_PINS[name]
        )
    for name, pin in runner.ARCH134_D1S2_PREDECESSOR_AST_PINS.items():
        assert (
            runner._arch134_d1s2_runner_ast_pin(name, pin)
            == runner.ARCH134_D1S2_SUCCESSOR_AST_PINS[name]
        )
        with pytest.raises(ValueError):
            runner._arch134_d1s2_runner_ast_pin(name, "a" * 64)


def test_lost_ack_readback_never_reports_success_or_retries(harness, monkeypatch):
    original = harness.storage.append
    calls = []

    def append(name, expected, data):
        row = json.loads(data)
        if row["data"].get("stage") != "ACK":
            original(name, expected, data)

    monkeypatch.setattr(harness.storage, "append", append)
    assert (
        start(
            harness,
            quote=lambda: calls.append(1) or contract.QuoteDisposition.NO_SIGNAL,
        )
        is contract.SessionTerminal.INDETERMINATE
    )
    with pytest.raises(ValueError):
        start(harness, quote=fail)
    assert calls == [1]
    rows = store.SuccessorJournal(harness.storage, harness.lineage, 1).read().rows
    assert rows[-1]["data"]["stage"] == "ENTRY_ADMITTED"


def test_session_two_cannot_enter_during_session_one(harness):
    calls = []

    def quote():
        second_process(harness)
        with pytest.raises(ValueError):
            start(harness, quote=lambda: calls.append("illegal"))
        harness.observations.process = admission.ManualProcessObservation(
            100, "windows-filetime:1000", contract.SESSIONS[0]
        )
        return contract.QuoteDisposition.NO_SIGNAL

    assert start(harness, quote=quote) is contract.SessionTerminal.NO_SIGNAL
    assert not calls
    assert harness.storage.read(contract.SESSION_NAMES[1]) is None


def test_child_terminal_and_parent_cross_digest_tampering_rejected(harness):
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    name = contract.SESSION_NAMES[0]
    rows = [json.loads(line) for line in harness.storage.read(name).splitlines()]
    rows[-1]["data"]["terminal"] = "RISK_REJECTED"
    data = b"".join(contract.canonical(row) + b"\n" for row in rows)
    with pytest.raises(ValueError):
        store.replay(data, harness.lineage, 1)
    rows[-1]["data"]["terminal"] = "NO_SIGNAL"
    rows[0]["grant_prefix"] = "a" * 64
    (harness.root / name).write_bytes(
        b"".join(contract.canonical(row) + b"\n" for row in rows)
    )
    with pytest.raises(ValueError):
        controller.snapshot(harness.storage, harness.lineage)


def test_foreign_namespace_is_preserved_without_reservation(harness):
    foreign = harness.root / "foreign.json"
    foreign.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        start(harness, quote=fail)
    assert foreign.read_bytes() == b"preserve"
    assert not (harness.root / contract.PARENT_NAME).exists()


def test_fsync_precedes_readback_and_ack(harness, monkeypatch):
    syncs = []
    original = store.os.fsync

    def sync(fd):
        syncs.append(fd)
        original(fd)

    monkeypatch.setattr(store.os, "fsync", sync)
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    rows = controller.snapshot(harness.storage, harness.lineage)
    assert len(syncs) == len(rows.parent.rows) + sum(
        len(child.rows) for child in rows.children
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("sessions", ["2026-11-04", "2026-11-05"]),
        ("product", ["QQQ"]),
        ("ceilings", []),
    ],
)
def test_lineage_cannot_replace_frozen_semantics(harness, field, value):
    with pytest.raises(ValueError):
        contract.SuccessorLineage.from_facts(harness.lineage.facts() | {field: value})


def test_admission_names_bind_the_existing_exported_contracts():
    from trading_bot.supervised_release.binding import RUNTIME_BINDING_SCHEMA
    from trading_bot.supervised_release.model import MANIFEST_SCHEMA

    assert contract.ADMISSION_CONTRACTS[:2] == (MANIFEST_SCHEMA, RUNTIME_BINDING_SCHEMA)


def test_terminal_counters_reject_boolean_alias_and_arbitrary_parent_material(harness):
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    rows = [
        json.loads(line)
        for line in harness.storage.read(contract.SESSION_NAMES[0]).splitlines()
    ]
    rows[-1]["data"]["counters"]["child_grants"] = True
    with pytest.raises(ValueError):
        store.replay(
            b"".join(contract.canonical(r) + b"\n" for r in rows), harness.lineage, 1
        )
    second_process(harness)
    assert start(harness) is contract.SessionTerminal.NO_SIGNAL
    rows = [
        json.loads(line)
        for line in harness.storage.read(contract.PARENT_NAME).splitlines()
    ]
    rows[-1]["data"]["session_digests"] = {"provider_body": "forbidden"}
    with pytest.raises(ValueError):
        store.replay(
            b"".join(contract.canonical(r) + b"\n" for r in rows), harness.lineage, None
        )


@pytest.mark.parametrize("disposition", list(contract.QuoteDisposition))
def test_closed_parent_replay_does_not_perform_another_admission(harness, disposition):
    assert start(harness, disposition) in contract.PROGRESSING
    second_process(harness)
    assert start(harness, disposition) in contract.PROGRESSING
    reads = harness.source.runtime.process_reads
    harness.source.runtime.process = replace(
        harness.source.runtime.process, isolated=False
    )
    assert start(harness, quote=fail, paper=fail) == "SERIES_COMPLETED"
    assert harness.source.runtime.process_reads == reads


def test_paper_pre_entry_rejection_reserves_no_mutation(harness):
    calls = []
    guards = iter((True, False))
    assert (
        start(
            harness,
            disposition=contract.QuoteDisposition.PAPER_REQUIRED,
            guard=lambda: next(guards),
            paper=lambda: calls.append(1),
        )
        is contract.SessionTerminal.BLOCKED
    )
    assert not calls
    counts = controller.snapshot(harness.storage, harness.lineage).counters
    assert counts["paper_attempts"] == counts["provider_entries"] == 1
    assert counts["paper_fills"] == 0
