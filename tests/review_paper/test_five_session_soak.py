"""F1 fake-only parent/window/evidence gate; production edges are never called."""

from __future__ import annotations

import ast
import copy
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from tests.review_paper.test_five_session_soak_child import SOURCE, Crash, Fake, instant

from trading_bot.review_paper import five_session_soak as c
from trading_bot.review_paper import five_session_soak_child as child
from trading_bot.review_paper import five_session_soak_store as s


class SeriesFake(Fake):
    def child(self, kind):
        if kind == "d1r8":
            self.execution.raw.calls.clear()
        super().child(kind)


@pytest.fixture
def fake(tmp_path):
    return SeriesFake(tmp_path)


def authorize(fake):
    return c.authorize(fake, SOURCE, c.INTERLOCK)


def payload(rows):
    return b"".join(s.canonical(r) + b"\n" for r in rows)


@pytest.mark.parametrize(
    "at,first",
    [
        ("2026-10-19T08:00", "2026-10-19"),
        ("2026-10-19T15:54:59", "2026-10-19"),
        ("2026-10-19T15:55", "2026-10-20"),
        ("2026-10-17T12:00", "2026-10-19"),
        ("2026-11-26T12:00", "2026-11-27"),
        ("2026-11-27T12:54:59", "2026-11-27"),
        ("2026-11-27T12:55", "2026-11-30"),
        ("2026-10-30T17:00", "2026-11-02"),
        ("2027-03-12T17:00", "2027-03-15"),
    ],
)
def test_exact_five_published_window(at, first):
    result = c.select_window(instant(at))
    assert len(result) == 5 and result[0] == first
    authority = c.NYSEPublishedRegularSessionAuthority()
    assert all(authority.schedule_for(datetime.fromisoformat(t).date()) for t in result)
    for a, b in zip(result, result[1:], strict=False):
        day = datetime.fromisoformat(a).date() + timedelta(days=1)
        while authority.schedule_for(day) is None:
            day += timedelta(days=1)
        assert b == day.isoformat()


@pytest.mark.parametrize(
    "at",
    [datetime(2026, 10, 20), instant("2029-01-02T12:00"), instant("2028-12-28T12:00")],
)
def test_naive_unpublished_or_incomplete_window_rejects(at):
    with pytest.raises(ValueError):
        c.select_window(at)


def test_parent_identity_excludes_clock_runtime_and_paths(fake):
    a = c.make_facts(SOURCE, instant("2026-10-19T08:00"), fake.binding)
    b = c.make_facts(SOURCE, instant("2026-10-19T09:00"), fake.binding)
    b["runtime"] = copy.deepcopy(b["runtime"])
    b["runtime"]["paper"]["inode"] += 1
    assert s.domain_id(a) == s.domain_id(b)
    b["source"] = dict(SOURCE, head="e" * 40)
    assert s.domain_id(a) != s.domain_id(b)
    assert s.reservation_name(a) == s.PARENT_NAME


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "date",
        "sixth",
        "duplicate",
        "reorder",
        "decimal",
        "uuid",
        "source",
        "scheduler",
        "bool_effect",
        "float_effect",
        "timestamp",
        "binding",
    ],
)
def test_canonical_closed_store_rejects_mutations(fake, mutation):
    journal = authorize(fake)
    rows = copy.deepcopy(journal.rows)
    if mutation == "unknown":
        rows[0]["extra"] = 0
    elif mutation == "missing":
        del rows[0]["facts"]["policy"]
    elif mutation == "date":
        rows[0]["facts"]["targets"][0] = "20261019"
    elif mutation == "sixth":
        rows[0]["facts"]["targets"].append("2026-10-26")
    elif mutation == "duplicate":
        rows[0]["facts"]["targets"][1] = rows[0]["facts"]["targets"][0]
    elif mutation == "reorder":
        rows[0]["facts"]["targets"].reverse()
    elif mutation == "decimal":
        rows[0]["facts"]["policy"]["starting_synthetic_cash"] = "10000.0"
    elif mutation == "uuid":
        rows[0]["identity"] = rows[0]["identity"].upper()
    elif mutation == "source":
        rows[0]["facts"]["d1r8"]["head"] = "f" * 40
    elif mutation == "scheduler":
        rows[0]["facts"]["scheduler"]["wake"] = True
    elif mutation == "bool_effect":
        rows[0]["effects"]["scheduler_creates"] = False
    elif mutation == "float_effect":
        rows[0]["effects"]["scheduler_creates"] = 0.0
    elif mutation == "timestamp":
        rows[0]["observed_at"] = rows[0]["observed_at"].replace("+00:00", "Z")
    else:
        rows[-1]["binding"] = "a" * 64
    with pytest.raises(ValueError):
        s.parse(payload(rows))


@pytest.mark.parametrize(
    "transport",
    [b"", b"{}\n", b"\xef\xbb\xbf{}\n", b'{"x":1,"x":2}\n', b" " * (s.MAX_BYTES + 1)],
    ids=["empty", "empty-object", "bom", "duplicate-key", "overbound"],
)
def test_malformed_or_overbound_slot_never_repaired(fake, transport):
    path = fake.parent / s.PARENT_NAME
    path.write_bytes(transport)
    with pytest.raises((ValueError, FileExistsError)):
        authorize(fake)
    assert path.read_bytes() == transport and fake.children == []


def test_append_order_and_fsync_readback(fake, monkeypatch):
    calls = []
    original = s.os.fsync
    monkeypatch.setattr(s.os, "fsync", lambda fd: (calls.append(fd), original(fd))[1])
    journal = authorize(fake)
    assert s.parse(journal.payload) == journal.rows
    assert len(calls) == len(journal.rows)
    with pytest.raises(ValueError):
        journal.append("SESSION_2_GRANT_INTENT", fake.now)
    with pytest.raises(ValueError):
        journal.append("FINAL", fake.now, classification="COMPLETED")
    journal.path.write_bytes(journal.payload + b" ")
    with pytest.raises(ValueError):
        journal.append("FINAL", fake.now, classification="BLOCKED")


def test_parent_slot_is_consumed_even_after_final(fake):
    journal = authorize(fake)
    c.finish(fake, journal, "BLOCKED")
    with pytest.raises(FileExistsError):
        authorize(fake)
    assert c.step(fake, s.Journal.load(journal.path)) == "BLOCKED"
    assert fake.events.count("scheduler_run") == 1


@pytest.mark.parametrize("ordinal", [0, 6, True, 1.0])
def test_invalid_or_sixth_grant_cannot_exist(fake, ordinal):
    journal = authorize(fake)
    with pytest.raises(ValueError):
        s.grant_facts(journal, ordinal, fake.binding)


@pytest.mark.parametrize("ordinal", [1, 2, 3, 4, 5])
def test_each_grant_binds_parent_prefix_target_and_runtime(fake, ordinal):
    journal = authorize(fake)
    # Complete predecessors using actual fake D1R7/D1R8 reducers first.
    for index in range(1, ordinal):
        fake.now = instant(journal.facts["targets"][index - 1] + "T10:00")
        assert c.step(fake, journal) == "NEXT_SESSION_WAIT"
    journal.append(f"SESSION_{ordinal}_GRANT_INTENT", fake.now)
    facts = s.grant_facts(journal, ordinal, fake.binding)
    grant = s.Journal.reserve(fake.parent, facts, observed_at=fake.now)
    s.admit_grant(journal, grant)
    assert facts["parent_id"] == journal.domain_id
    assert facts["target_session"] == journal.facts["targets"][ordinal - 1]
    assert (
        facts["parent_prefix"]["sha256"] == hashlib.sha256(journal.payload).hexdigest()
    )
    with pytest.raises(FileExistsError):
        s.Journal.reserve(fake.parent, facts)
    altered = copy.deepcopy(grant.facts)
    altered["parent_prefix"]["sha256"] = "f" * 64
    rows = copy.deepcopy(grant.rows)
    rows[0]["facts"] = altered
    rows[0]["binding"] = s.digest(altered)
    forged = s.Journal(grant.path, payload(rows), grant.identity)
    with pytest.raises(ValueError):
        s.admit_grant(journal, forged)


@pytest.mark.parametrize("outcome", ["NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"])
def test_five_operational_progression_terminals_and_ordered_final_proof(fake, outcome):
    journal = authorize(fake)
    if outcome == "NO_SIGNAL":
        fake.execution.raw.closes = (10, 10, 10, 10)
    elif outcome == "RISK_REJECTED":
        fake.execution.rh.price = "1000000000000"
    for index, target in enumerate(journal.facts["targets"], 1):
        fake.now = instant(target + "T10:00")
        assert c.step(fake, journal) == (
            "COMPLETED" if index == 5 else "NEXT_SESSION_WAIT"
        )
    final = journal.rows[-1]
    assert final["classification"] == "COMPLETED"
    expected = [outcome] * 5
    if outcome == "PAPER_EXECUTED":
        expected = ["PAPER_EXECUTED"] + ["NO_SIGNAL"] * 4
    assert [v["classification"] for v in final["proof"]["children"]] == expected
    assert [v["target_session"] for v in final["proof"]["children"]] == journal.facts[
        "targets"
    ]
    assert final["effects"]["child_grants"] == 5
    for key in ("d1r7_attempts", "d1r8_attempts"):
        assert sum(v["effects"][key] for v in final["proof"]["children"]) == 5
    assert fake.children == ["d1r7", "d1r8"] * 5
    assert s.parse(journal.payload) == journal.rows
    before = list(fake.children)
    assert (
        c.step(fake, s.Journal.load(journal.path)) == "COMPLETED"
        and fake.children == before
    )
    for proof in final["proof"]["children"]:
        s.summary(proof, journal.facts, proof["ordinal"])
        assert proof["contract"]["source_head"] == s.D1R8["head"]
        assert proof["d1r7"] and proof["d1r8"]
        assert all(
            proof["d1r8_effects"][k] == 0 for k, v in s.D1R8_BUDGETS.items() if v == 0
        )


@pytest.mark.parametrize("outcome", ["SESSION_MISSED", "BLOCKED", "INDETERMINATE"])
def test_halt_never_grants_a_later_target(fake, outcome, monkeypatch):
    journal = authorize(fake)
    fake.now = instant("2026-10-19T10:00")
    if outcome == "SESSION_MISSED":
        fake.now = instant("2026-10-20T10:00")
    elif outcome == "BLOCKED":
        fake.drift = "source"
    else:
        fake.child_fault = "d1r7"
    assert c.step(fake, journal) == outcome
    before = list(fake.children)
    for target in journal.facts["targets"][1:]:
        fake.now = instant(target + "T10:00")
        assert c.step(fake, s.Journal.load(journal.path)) == outcome
    assert fake.children == before
    assert journal.rows[-1]["effects"]["child_grants"] <= 1
    assert not any(r["event"] == "SESSION_2_GRANT_INTENT" for r in journal.rows)


@pytest.mark.parametrize(
    "phase",
    ["SCHEDULER_CREATE_INTENT", "SCHEDULER_RUN_INTENT", "SESSION_1_GRANT_INTENT"],
)
def test_restart_after_intent_never_reenters_effect(fake, phase):
    facts = c.make_facts(SOURCE, fake.now, fake.binding)
    journal = s.Journal.reserve(fake.parent, facts)
    events = ["SOURCES_ADMITTED", "WINDOW_BOUND"]
    if phase == "SCHEDULER_CREATE_INTENT":
        events += [phase]
    else:
        events += ["SOAK_READY", "SCHEDULER_RUN_INTENT"]
        if phase == "SESSION_1_GRANT_INTENT":
            events += ["SCHEDULER_RUN_ACK", phase]
    for event in events:
        journal.append(event, fake.now)
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert (
        fake.children == []
        and "scheduler_create" not in fake.events
        and "scheduler_run" not in fake.events
    )


def test_wait_restart_and_clock_regression(fake):
    journal = authorize(fake)
    with pytest.raises(Crash):
        c.supervise(fake, journal)
    assert fake.waits == [60]
    resumed = s.Journal.load(journal.path)
    assert c.step(fake, resumed) == "NEXT_SESSION_WAIT"
    fake.now -= timedelta(seconds=1)
    assert c.step(fake, resumed) == "INDETERMINATE"
    assert fake.children == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "reorder",
        "digest",
        "counter",
        "contract",
        "classification",
        "scheduler",
    ],
)
def test_end_window_proof_rejects_mutations(fake, mutation):
    journal = authorize(fake)
    fake.execution.raw.closes = (10, 10, 10, 10)
    for target in journal.facts["targets"]:
        fake.now = instant(target + "T10:00")
        c.step(fake, journal)
    rows = copy.deepcopy(journal.rows)
    end = rows[-1]["proof"]
    if mutation == "missing":
        end["children"].pop()
    elif mutation == "reorder":
        end["children"].reverse()
    elif mutation == "digest":
        end["children"][0]["child_journal"]["sha256"] = "f" * 64
    elif mutation == "counter":
        end["children"][0]["effects"]["d1r7_attempts"] = 0
    elif mutation == "contract":
        end["children"][0]["contract"]["symbol"] = "QQQ"
    elif mutation == "classification":
        end["children"][0]["classification"] = "BLOCKED"
    else:
        end["scheduler"] = "ABSENT"
    with pytest.raises(ValueError):
        s.parse(payload(rows))


def test_controller_has_no_research_or_promotion_capability():
    for module in (c, child, s):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [
            ast.unparse(n)
            for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        assert all("experiments" not in v for v in imports)
        assert "ResearchStrategyPaperSessionObservation" not in source
        assert "ResearchStrategyPaperCandidateEligibility" not in source
        assert "AUTHORIZE_ARCH134_D1R9" not in source
    assert s.CEILINGS["real_money"] == s.CEILINGS["promotion"] == s.CEILINGS["d2"] == 0


def test_v1_source_is_unchanged():
    root = Path(__file__).resolve().parents[2]
    expected = {
        (
            "src/trading_bot/experiments/"
            "research_strategy_paper_evidence_verification.py"
        ): ("915bdd84bee3ad0b57efcafb0a78da01fce94e66"),
        (
            "src/trading_bot/experiments/"
            "research_strategy_paper_candidate_eligibility.py"
        ): ("fd6b0ad650fb3fb97f587deb7cffc7286e685813"),
    }
    for path, pin in expected.items():
        data = (root / path).read_bytes().replace(b"\r\n", b"\n")
        assert (
            hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            == pin
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "bytes", "terminal", "d1r7", "d1r8", "scheduler"]
)
def test_previous_evidence_drift_blocks_later_effects(fake, mutation):
    journal = authorize(fake)
    fake.now = instant("2026-10-19T10:00")
    assert c.step(fake, journal) == "NEXT_SESSION_WAIT"
    records = c.children(journal)
    path = records[0].path
    if mutation == "missing":
        path.unlink()  # Disposable test evidence only.
    elif mutation == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "terminal":
        rows = copy.deepcopy(records[0].rows)
        rows[-1]["classification"] = "NO_SIGNAL"
        path.write_bytes(payload(rows))
    elif mutation == "d1r7":
        fake.execution.predecessor.write_bytes(b"corrupt\n")
    elif mutation == "d1r8":
        fake.execution.output.write_bytes(b"corrupt\n")
    else:
        fake.scheduler = False
    before = list(fake.children)
    fake.now = instant("2026-10-20T10:00")
    if mutation == "scheduler":
        # Scheduler projection is a completion requirement; check read-only now.
        with pytest.raises(ValueError):
            c.reconcile_window(fake, journal)
    else:
        assert c.step(fake, journal) == "BLOCKED"
        assert fake.children == before


def test_f1_checkpoint_is_source_only_and_robinhood_owned():
    from scripts import checkpoint_runner as runner
    from scripts import run_test_certification as certification

    root = Path(__file__).resolve().parents[2]
    spec = runner._checkpoint_specs()[runner.ARCH134_F1_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == s.BRANCH
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), s.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] != "full"
    assert runner.ACTIVE_CI_CHECKPOINTS.count(spec.name) == 1
    assert runner._arch134_f1_authority_check(root) == ()
    inventory = certification.discover_inventory(root)
    assert len(certification.select_inventory(inventory, "robinhood")) == 111
    assert runner._batch_workflow_is_reviewed(
        (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "executable", "blob", "predecessor", "digest"]
)
def test_f1_additive_pin_overlay_fails_closed(monkeypatch, mutation):
    from scripts import checkpoint_runner as runner

    pins = dict(runner.ARCH134_F1_TEST_PIN_OVERRIDES)
    path = next(iter(pins))
    before = runner.ARCH134_F1_PREDECESSOR_TEST_PINS[path]
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/unknown.py"] = "a" * 40
    elif mutation == "executable":
        pins["src/trading_bot/review_paper/five_session_soak.py"] = "a" * 40
    elif mutation == "blob":
        pins[path] = "f" * 40
    elif mutation == "predecessor":
        before = "e" * 40
    else:
        monkeypatch.setattr(runner, "ARCH134_F1_TEST_PINS_SHA256", "b" * 64)
    monkeypatch.setattr(runner, "ARCH134_F1_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch134_f1_current_inventory_test_pin(path, before)


def test_scheduler_claim_is_durable_and_single_use(fake, monkeypatch):
    from scripts import arch134_f1_bridge as bridge

    monkeypatch.setattr(bridge, "PARENT", fake.parent)
    monkeypatch.setattr(bridge, "load_store", lambda: s)
    monkeypatch.setattr(bridge, "admit_sources", lambda facts: ())
    monkeypatch.setattr(bridge, "admit_runtime", lambda *a, **kw: None)
    monkeypatch.setattr(bridge.sys, "argv", ["fixed-bridge"])
    assert bridge.scheduler_claim() == "BLOCKED"
    journal = s.Journal.reserve(
        fake.parent, c.make_facts(SOURCE, fake.now, fake.binding)
    )
    for event in ("SOURCES_ADMITTED", "WINDOW_BOUND", "SCHEDULER_CREATE_INTENT"):
        journal.append(event, fake.now)
    assert bridge.scheduler_claim() == "CREATE"
    assert bridge.scheduler_claim() == "BLOCKED"
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert fake.events.count("scheduler_create") == 0


def test_fixed_contracts_equal_accepted_d1r7_public_contract(fake):
    from datetime import UTC

    from trading_bot.review_paper import d1_session_authorization as q

    for target in c.select_window(fake.now):
        at = datetime.fromisoformat(target + "T12:00:00+00:00").astimezone(UTC)
        plan = q.Plan(q.Source(**s.D1R7), q.Source(**s.D1R8), at)
        assert plan.facts["strategy_contract"] == s.contract(target)
        assert plan.facts["d1_policy"] == s.POLICY
