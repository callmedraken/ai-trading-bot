from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import PureWindowsPath
from types import SimpleNamespace

import pytest
from tests.review_paper.test_arch134_f1r1_d1s4_rename_free_direct_installation import (
    readonly_git as readonly_git,
)
from tests.review_paper.test_arch134_readonly_deployment_admission_diagnostic_r1 import (  # noqa: E501
    dispatch_fake,
    r1_fake,
)

from scripts import checkpoint_runner as runner
from trading_bot.supervised_release import deployment_admission as readonly
from trading_bot.supervised_release import deployment_admission_diagnostic_r1 as r1
from trading_bot.supervised_release import deployment_admission_diagnostic_r2 as r2
from trading_bot.supervised_release import (
    deployment_admission_diagnostic_r2_host as host,
)
from trading_bot.supervised_release import deployment_admission_source as source
from trading_bot.supervised_release.deployment_candidate import (
    INCIDENT_RELEASE_IDS,
    INCIDENT_ROOTS,
)
from trading_bot.supervised_release.installation_contract import ANCESTORS

PRESERVED = tuple(PureWindowsPath(path).name for path in INCIDENT_ROOTS)


def r2_fake():
    fake = r1_fake()
    fake.invocation = r2.ReviewedInvocation(
        replace(fake.invocation.observer, reference=r2.BRANCH),
        fake.invocation.principal_sid,
        fake.invocation.elevated,
    )
    fake.source_value = replace(fake.source_value, observer=fake.invocation.observer)
    return fake


def run(fake):
    result = r2.admission(fake.invocation, fake, fake)
    assert result["effects"] == dict.fromkeys(readonly.ZERO_EFFECTS, 0)
    assert result["authority"] == dict.fromkeys(readonly.NO_AUTHORITY, False)
    r2.verify_evidence(r2.encode_evidence(result), expected=result)
    return result


@pytest.mark.parametrize("name", PRESERVED)
def test_consumed_r1_contradiction_remains_truthful(name):
    fake = r1_fake()
    fake.namespace = (name,)
    result = r1.admission(fake.invocation, fake, fake)
    assert result["status"] == "BLOCKED" and result["reason"] == "HOST"
    assert result["diagnostic_code"] == r1.HOST_FORBIDDEN_IDENTITY
    assert all(value == 0 for value in result["effects"].values())
    assert all(value is False for value in result["authority"].values())


@pytest.mark.parametrize("mask", range(8))
def test_frozen_incidents_are_optional_opaque_parent_metadata(mask):
    fake = r2_fake()
    fake.namespace = tuple(name for i, name in enumerate(PRESERVED) if mask & (1 << i))
    before = (fake.source_value, fake.security_value, fake.quiet_value)
    result = run(fake)
    assert result["status"] == "PASS" and result["reason"] == readonly.READY
    assert fake.source_count == 2 and fake.events.count("parent_names") == 2
    assert all(
        event[1] in ANCESTORS for event in fake.events if isinstance(event, tuple)
    )
    assert before == (fake.source_value, fake.security_value, fake.quiet_value)
    assert result["destination"].endswith(fake.source_value.manifest.release_id)
    assert not any(name.encode() in r2.encode_evidence(result) for name in PRESERVED)
    empty = r2_fake()
    empty_result = run(empty)
    for key in ("source", "manifest", "destination", "effects", "authority"):
        assert result[key] == empty_result[key]
    assert r2.PRESERVED_INCIDENT_NAMES == frozenset(PRESERVED)


@pytest.mark.parametrize("identifier", INCIDENT_RELEASE_IDS)
@pytest.mark.parametrize(
    "suffix",
    [".alias", ".partial", "-other", "x", ".installing.extra", ".", " ", "/child"],
)
def test_all_other_incident_prefix_forms_rejected(identifier, suffix):
    fake = r2_fake()
    fake.namespace = (identifier + suffix,)
    assert run(fake)["diagnostic_code"] == r2.HOST_INCIDENT_ALIAS


@pytest.mark.parametrize(
    "name",
    [
        INCIDENT_RELEASE_IDS[0] + ".installing",
        INCIDENT_RELEASE_IDS[1],
        INCIDENT_RELEASE_IDS[2],
        *(name.upper() for name in PRESERVED),
        PRESERVED[1].replace(".installing", ".Installing"),
    ],
)
def test_alternate_final_installing_and_case_variants_rejected(name):
    fake = r2_fake()
    fake.namespace = (name,)
    assert run(fake)["diagnostic_code"] == r2.HOST_INCIDENT_ALIAS


@pytest.mark.parametrize(
    "suffix",
    ["", ".installing", ".partial", "-stage", "x", ".alias", ".", "/child", " "],
)
@pytest.mark.parametrize("uppercase", [False, True])
def test_prospective_destination_and_every_prefix_form_remain_forbidden(
    suffix, uppercase
):
    fake = r2_fake()
    name = fake.source_value.manifest.release_id + suffix
    fake.namespace = (name.upper() if uppercase else name,)
    assert run(fake)["diagnostic_code"] == r2.HOST_DESTINATION_PRESENT


def test_canonical_nonincident_historical_release_remains_permitted():
    fake = r2_fake()
    fake.namespace = ("release-aaaaaaaaaaaa5aaa8aaaaaaaaaaaaaaa", *PRESERVED)
    assert run(fake)["status"] == "PASS"


@pytest.mark.parametrize(
    "name",
    [
        "bad",
        "release-" + "a" * 32,
        "RELEASE-" + "a" * 32,
        "..",
        "",
        "release-aaaaaaaaaaaa5aaa8aaaaaaaaaaaaaaa.installing",
        "a/b",
        "noncanonical",
        1,
    ],
)
def test_malformed_noncanonical_names_fail_namespace_policy(name):
    fake = r2_fake()
    fake.namespace = (name,)
    assert run(fake)["diagnostic_code"] == r2.HOST_NAMESPACE_POLICY


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_name",
        "duplicate_id",
        "file",
        "reparse",
        "short_name",
        "bad_id",
        "shape",
    ],
)
def test_parent_metadata_guards_are_unchanged(monkeypatch, mutation):
    fake = r2_fake()
    entry = (PRESERVED[0], 100, 0x10, "")
    entries = (entry,)
    if mutation == "duplicate_name":
        entries = (entry, (PRESERVED[0], 101, 0x10, ""))
    elif mutation == "duplicate_id":
        entries = (entry, (PRESERVED[1], 100, 0x10, ""))
    elif mutation == "file":
        entries = ((PRESERVED[0], 100, 0, ""),)
    elif mutation == "reparse":
        entries = ((PRESERVED[0], 100, 0x410, ""),)
    elif mutation == "short_name":
        entries = ((PRESERVED[0], 100, 0x10, "RELEAS~1"),)
    elif mutation == "bad_id":
        entries = ((PRESERVED[0], 0, 0x10, ""),)
    else:
        entries = ((PRESERVED[0],),)
    monkeypatch.setattr(fake, "namespace_metadata", lambda: entries)
    assert run(fake)["diagnostic_code"] == r2.HOST_NAMESPACE_POLICY


@pytest.mark.parametrize(
    "error",
    [
        ValueError("secret arbitrary path"),
        RuntimeError("INCIDENT_ALIAS"),
        ValueError("DESTINATION_PRESENT", "secret"),
        KeyboardInterrupt("secret"),
    ],
)
def test_unknown_namespace_failures_are_closed_host_unknown(monkeypatch, error):
    fake = r2_fake()

    def fail(*args):
        raise error

    monkeypatch.setattr(r2, "safe_namespace_names", fail)
    result = run(fake)
    assert result["diagnostic_code"] == r2.HOST_UNKNOWN
    assert b"secret" not in r2.encode_evidence(result)


def test_security_source_and_quiescence_remain_r1_semantics():
    # All shared collectors/validators and the evidence ceiling remain identical.
    before = ast.parse(runner.Path(r1.__file__).read_text())
    after = ast.parse(runner.Path(r2.__file__).read_text())

    def functions(tree):
        return {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    old, new = functions(before), functions(after)
    for name in old.keys() - {"_namespace_policy_code", "_snapshot"}:
        assert ast.dump(old[name]) == ast.dump(new[name]), name
    snapshot = ast.dump(old["_snapshot"]).replace(
        "Attribute(value=Name(id='readonly', ctx=Load()), "
        "attr='safe_namespace_names', ctx=Load())",
        "Name(id='safe_namespace_names', ctx=Load())",
    )
    assert snapshot == ast.dump(new["_snapshot"])
    assert r2.MAX_EVIDENCE_BYTES == r1.MAX_EVIDENCE_BYTES == 4 * 1024 * 1024
    assert r2.ZERO_EFFECTS == r1.ZERO_EFFECTS and r2.NO_AUTHORITY == r1.NO_AUTHORITY
    assert r2.DIAGNOSTIC_CODES == (
        r1.DIAGNOSTIC_CODES - {r1.HOST_FORBIDDEN_IDENTITY}
    ) | {r2.HOST_INCIDENT_ALIAS, r2.HOST_DESTINATION_PRESENT}


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("index", r2.HOST_SOURCE_CHECKOUT_POLICY),
        ("lineage", r2.HOST_SOURCE_LINEAGE),
        ("inventory", r2.HOST_SOURCE_INVENTORY),
        ("collection", r2.HOST_SOURCE_GIT_COLLECTION),
    ],
)
def test_r2_actual_source_reader_retains_closed_failures(
    monkeypatch, readonly_git, mutation, code
):
    fake = r2_fake()
    invocation, calls = dispatch_fake(monkeypatch, readonly_git, r2.BRANCH)
    fake.invocation = r2.ReviewedInvocation(
        invocation.observer, fake.invocation.principal_sid, False
    )
    if mutation == "index":
        readonly_git.responses[("ls-files", "-v", "-z")] = b"h hidden\0"
    elif mutation == "lineage":
        readonly_git.responses[
            ("merge-base", readonly.DESIGN.head, invocation.observer.head)
        ] = b"f" * 40
    elif mutation == "inventory":
        readonly_git.batch += b"raw-secret-trailing-data"
    else:
        monkeypatch.setattr(
            source.subprocess,
            "run",
            lambda *a, **k: SimpleNamespace(
                returncode=1, stdout=b"secret", stderr=b"secret"
            ),
        )
    reader = host.R2LocalGitReader(readonly_git.root)
    monkeypatch.setattr(fake, "source", lambda inv: source.observe_source(reader, inv))
    monkeypatch.setattr(fake, "read_session", lambda _: pytest.fail("host entered"))
    assert run(fake)["diagnostic_code"] == code


def test_r2_fixed_binding_and_complete_first_source_observation(
    monkeypatch, readonly_git
):
    invocation, calls = dispatch_fake(monkeypatch, readonly_git, r2.BRANCH)
    reader = host.R2LocalGitReader(readonly_git.root)
    result = source.observe_source(reader, invocation)
    assert result.observer == invocation.observer
    assert reader.diagnostic_process_starts == len(calls) == 23
    assert calls[9] == ("rev-parse", "refs/remotes/origin/" + r2.BRANCH)
    for branch in (
        readonly.BRANCH,
        r1.BRANCH,
        "feature/arbitrary",
        r2.BRANCH + "-alias",
    ):
        with pytest.raises(ValueError, match="^GIT_VOCABULARY$"):
            reader.query("rev-parse", "refs/remotes/origin/" + branch)
    assert len(calls) == 23


def test_host_entry_uses_only_fakes_and_fixed_r2_binding(monkeypatch):
    fake = r2_fake()
    for name, value in {
        "HEAD": fake.invocation.observer.head,
        "TREE": fake.invocation.observer.tree,
        "REFERENCE": r2.BRANCH,
        "PRINCIPAL_SID": fake.invocation.principal_sid,
        "ELEVATED": "false",
    }.items():
        monkeypatch.setenv(host.PREFIX + name, value)

    def collect(root, reader):
        assert reader._tracking_branch == r2.BRANCH
        assert reader.diagnostic_process_starts == 0
        return fake

    fake.diagnostic_process_starts = 0
    fake.namespace = PRESERVED
    monkeypatch.setattr(host, "HostCollectors", collect)
    monkeypatch.setattr(host, "HostReader", lambda _: fake)
    monkeypatch.setattr(
        source.subprocess, "run", lambda *a, **k: pytest.fail("process")
    )
    result = host.preflight()
    assert result["status"] == "PASS" and result["diagnostic_process_starts"] == 0


@pytest.mark.parametrize("count", [False, -1, 1001, "23"])
def test_r2_evidence_remains_bounded_and_closed(count):
    fake = r2_fake()
    result = run(fake)
    with pytest.raises(ValueError):
        r2.encode_evidence({**result, "diagnostic_process_starts": count})
    with pytest.raises(ValueError):
        r2.encode_evidence({**result, "namespace_names": list(PRESERVED)})
    for key in result["authority"]:
        with pytest.raises(ValueError):
            r2.encode_evidence(
                {**result, "authority": {**result["authority"], key: True}}
            )
    for key in result["effects"]:
        with pytest.raises(ValueError):
            r2.encode_evidence({**result, "effects": {**result["effects"], key: 1}})


def test_r2_exact_registration_and_unchanged_r1_security_source():
    root = runner.Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[r2.CHECKPOINT]
    assert spec.remote_branch == r2.BRANCH
    assert spec.preflight is runner._arch134_readonly_diagnostic_r2_preflight
    assert spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), r2.BRANCH, "push")
        == r2.CHECKPOINT
    )
    assert runner.CI_CERTIFICATION_PROFILES[r2.CHECKPOINT] == "robinhood"
    assert len(spec.tests) == len(set(spec.tests))
    assert runner._arch134_readonly_diagnostic_r2_authority_check(root) == ()
    assert runner._arch134_readonly_diagnostic_r1_authority_check(root) == ()


def test_r2_runner_rejects_existing_evidence_before_any_observer(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner, "_arch134_readonly_diagnostic_r2_authority_check", lambda _: ()
    )
    spec = runner._checkpoint_specs()[r2.CHECKPOINT]
    with pytest.raises(RuntimeError, match="fresh evidence root required"):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path / "source", evidence_root=tmp_path
        )


@pytest.mark.parametrize(
    "reference",
    [r1.BRANCH, readonly.BRANCH, "develop", "feature/arbitrary", r2.BRANCH + "-alias"],
)
def test_r2_invocation_never_accepts_other_source_branches(reference):
    fake = r2_fake()
    with pytest.raises(ValueError, match="^REVIEWED_OBSERVER_SOURCE_REQUIRED$"):
        r2.ReviewedInvocation(
            replace(fake.invocation.observer, reference=reference),
            fake.invocation.principal_sid,
            False,
        )


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("token", r2.HOST_TOKEN_POLICY),
        ("privilege", r2.HOST_TOKEN_POLICY),
        ("sacl", r2.HOST_SACL_POLICY),
        ("python", r2.HOST_RUNTIME_PYTHON_IDENTITY),
        ("process", r2.HOST_QUIESCENCE_POLICY),
        ("scheduler", r2.HOST_QUIESCENCE_POLICY),
        ("drift", r2.HOST_UNKNOWN),
        ("source", r2.HOST_SOURCE_LINEAGE),
    ],
)
def test_preserved_entries_do_not_bypass_security_quiescence_or_stability(
    mutation, code
):
    fake = r2_fake()
    fake.namespace = PRESERVED
    if mutation == "token":
        fake.security_value = replace(
            fake.security_value,
            token=replace(fake.security_value.token, user_sid="S-1-5-18"),
        )
    elif mutation == "privilege":
        fake.security_value = replace(
            fake.security_value, privileges=(("SeDebugPrivilege", 2),)
        )
    elif mutation == "sacl":
        fake.security_value = replace(fake.security_value, sacl_status="BAD")
    elif mutation == "python":
        fake.security_value = replace(
            fake.security_value, python_identity=fake.security_value.runtime_identity
        )
    elif mutation == "process":
        fake.quiet_value = replace(fake.quiet_value, relevant_process_count=1)
    elif mutation == "scheduler":
        fake.quiet_value = replace(fake.quiet_value, reboot_manual_start=False)
    elif mutation == "source":
        fake.source_value = replace(fake.source_value, r1_state="UNCONSUMED")
    else:
        fake.drift = True
    assert run(fake)["diagnostic_code"] == code


def test_arbitrary_diagnostic_code_is_never_serialized():
    fake = r2_fake()
    result = run(fake)
    invalid = {
        "schema": r2.SCHEMA,
        "status": "BLOCKED",
        "reason": "HOST",
        "diagnostic_code": "raw-secret-name",
        "effects": result["effects"],
        "authority": result["authority"],
    }
    with pytest.raises(ValueError, match="BLOCK_DIAGNOSTIC"):
        r2.encode_evidence(invalid)


def test_r2_authority_enforces_both_new_security_sources(monkeypatch):
    root = runner.Path(runner.__file__).resolve().parents[1]
    expected = {
        "src/trading_bot/supervised_release/deployment_admission_diagnostic_r2.py",
        "src/trading_bot/supervised_release/deployment_admission_diagnostic_r2_host.py",
    }
    assert set(runner.ARCH134_READONLY_DIAGNOSTIC_R2_SOURCE_PINS) == expected
    original = runner._authority_blob_matches
    for relative in expected:

        def check(repo, path, pin, relative=relative):
            return False if path == root / relative else original(repo, path, pin)

        monkeypatch.setattr(runner, "_authority_blob_matches", check)
        assert (
            "Diagnostic R2 security source drift: " + relative
            in runner._arch134_readonly_diagnostic_r2_authority_check(root)
        )
