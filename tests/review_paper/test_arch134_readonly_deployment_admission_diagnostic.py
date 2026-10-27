from __future__ import annotations

import json
from dataclasses import replace

import pytest
from tests.review_paper.test_arch134_f1r1_d1s4_rename_free_direct_installation import (
    ReadonlyFake,
)

from scripts import checkpoint_runner as runner
from trading_bot.supervised_release import (
    deployment_admission as readonly,
)
from trading_bot.supervised_release import (
    deployment_admission_diagnostic as diagnostic,
)
from trading_bot.supervised_release import (
    deployment_candidate as candidate,
)
from trading_bot.supervised_release.bundle import canonical_json
from trading_bot.supervised_release.installation_contract import ANCESTORS


def successor_fake() -> ReadonlyFake:
    fake = ReadonlyFake()
    fake.invocation = diagnostic.ReviewedInvocation(
        candidate.SourceIdentity(
            candidate.REPOSITORY, diagnostic.BRANCH, "c" * 40, "d" * 40
        ),
        fake.invocation.principal_sid,
        False,
    )
    fake.source_value = replace(fake.source_value, observer=fake.invocation.observer)
    return fake


def run_diagnostic(fake: ReadonlyFake) -> dict[str, object]:
    return diagnostic.admission(fake.invocation, fake, fake)


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("session", diagnostic.HOST_SESSION),
        ("parent", diagnostic.HOST_PARENT),
        ("ancestors", diagnostic.HOST_ANCESTORS),
        ("ancestor_volume", diagnostic.HOST_ANCESTORS),
        ("namespace_collection", diagnostic.HOST_NAMESPACE_COLLECTION),
        ("namespace_shape", diagnostic.HOST_NAMESPACE_POLICY),
        ("incident", diagnostic.HOST_FORBIDDEN_IDENTITY),
        ("prospective", diagnostic.HOST_FORBIDDEN_IDENTITY),
        ("security_collection", diagnostic.HOST_SECURITY_COLLECTION),
        ("wrong_sid", diagnostic.HOST_TOKEN_POLICY),
        ("token_mismatch", diagnostic.HOST_TOKEN_POLICY),
        ("privilege", diagnostic.HOST_TOKEN_POLICY),
        ("sacl", diagnostic.HOST_SACL_POLICY),
        ("runtime_alias", diagnostic.HOST_RUNTIME_PYTHON_IDENTITY),
        ("python_volume", diagnostic.HOST_RUNTIME_PYTHON_IDENTITY),
        ("quiescence_collection", diagnostic.HOST_QUIESCENCE_COLLECTION),
        ("process_overlap", diagnostic.HOST_QUIESCENCE_POLICY),
        ("manual_start", diagnostic.HOST_QUIESCENCE_POLICY),
        ("scheduler_shape", diagnostic.HOST_QUIESCENCE_POLICY),
        ("unknown", diagnostic.HOST_UNKNOWN),
    ],
)
def test_diagnostic_taxonomy_is_closed_and_boundary_specific(
    monkeypatch, mutation, expected
):
    fake = successor_fake()
    secret = "raw-secret=win32-0xdeadbeef"

    def failure(*args, **kwargs):
        raise RuntimeError(secret)

    if mutation == "session":
        monkeypatch.setattr(fake, "read_session", failure)
    elif mutation == "parent":
        monkeypatch.setattr(diagnostic.readonly, "observe_parent", failure)
    elif mutation == "ancestors":
        monkeypatch.setattr(diagnostic.readonly, "check_object", failure)
    elif mutation == "ancestor_volume":
        fake.nodes[ANCESTORS[0]] = replace(
            fake.nodes[ANCESTORS[0]], identity=(8, fake.nodes[ANCESTORS[0]].identity[1])
        )
        monkeypatch.setattr(
            diagnostic.readonly,
            "observe_parent",
            lambda session: fake.nodes[ANCESTORS[-1]],
        )
    elif mutation == "namespace_collection":
        monkeypatch.setattr(fake, "namespace_metadata", failure)
    elif mutation == "namespace_shape":
        monkeypatch.setattr(fake, "namespace_metadata", lambda: (("bad",),))
    elif mutation == "incident":
        fake.namespace = (candidate.INCIDENT_RELEASE_IDS[0],)
    elif mutation == "prospective":
        fake.namespace = (fake.source_value.manifest.release_id + ".installing",)
    elif mutation == "security_collection":
        monkeypatch.setattr(fake, "security", failure)
    elif mutation == "wrong_sid":
        fake.security_value = replace(
            fake.security_value,
            token=replace(fake.security_value.token, user_sid="S-1-5-18"),
        )
    elif mutation == "token_mismatch":
        fake.security_value = replace(
            fake.security_value,
            token=replace(fake.security_value.token, elevated=True),
        )
    elif mutation == "privilege":
        fake.security_value = replace(
            fake.security_value, privileges=(("SeDebugPrivilege", 2),)
        )
    elif mutation == "sacl":
        fake.security_value = replace(fake.security_value, sacl_status="BAD")
    elif mutation == "runtime_alias":
        fake.security_value = replace(
            fake.security_value,
            python_identity=fake.security_value.runtime_identity,
        )
    elif mutation == "python_volume":
        fake.security_value = replace(
            fake.security_value,
            runtime_identity=(8, fake.security_value.runtime_identity[1]),
        )
    elif mutation == "quiescence_collection":
        monkeypatch.setattr(fake, "quiescence", failure)
    elif mutation == "process_overlap":
        fake.quiet_value = replace(fake.quiet_value, relevant_process_count=1)
    elif mutation == "manual_start":
        fake.quiet_value = replace(fake.quiet_value, reboot_manual_start=False)
    elif mutation == "scheduler_shape":
        fake.quiet_value = replace(fake.quiet_value, tasks=(("bad", "bad"),))
    else:
        monkeypatch.setattr(diagnostic, "_snapshot", failure)

    result = run_diagnostic(fake)
    assert result == {
        "schema": diagnostic.SCHEMA,
        "status": "BLOCKED",
        "reason": "HOST",
        "diagnostic_code": expected,
        "effects": dict.fromkeys(readonly.ZERO_EFFECTS, 0),
        "authority": dict.fromkeys(readonly.NO_AUTHORITY, False),
    }
    payload = diagnostic.encode_evidence(result)
    assert payload == canonical_json(result).encode("utf-8")
    assert len(payload) <= diagnostic.MAX_EVIDENCE_BYTES
    assert secret.encode() not in payload
    assert b"0xdeadbeef" not in payload
    assert "diagnostic_code" in json.loads(payload)


def test_diagnostic_process_count_is_optional_but_strict():
    result = {
        "schema": diagnostic.SCHEMA,
        "status": "BLOCKED",
        "reason": "HOST",
        "diagnostic_code": diagnostic.HOST_UNKNOWN,
        "diagnostic_process_starts": 23,
        "effects": dict.fromkeys(readonly.ZERO_EFFECTS, 0),
        "authority": dict.fromkeys(readonly.NO_AUTHORITY, False),
    }
    diagnostic.verify_evidence(diagnostic.encode_evidence(result), expected=result)
    for mutation in (
        {**result, "diagnostic_code": "raw-error"},
        {**result, "extra": False},
        {key: value for key, value in result.items() if key != "diagnostic_code"},
    ):
        with pytest.raises(ValueError):
            diagnostic.encode_evidence(mutation)


def test_successor_pass_preserves_v1_pass_semantics_without_authority():
    result = run_diagnostic(successor_fake())
    assert result["schema"] == diagnostic.SCHEMA
    assert result["status"] == "PASS"
    assert result["reason"] == diagnostic.READY
    assert "diagnostic_code" not in result
    assert result["effects"] == dict.fromkeys(readonly.ZERO_EFFECTS, 0)
    assert result["authority"] == dict.fromkeys(readonly.NO_AUTHORITY, False)
    diagnostic.verify_evidence(diagnostic.encode_evidence(result), expected=result)


def test_predecessor_v1_remains_coarse_and_does_not_emit_successor_code():
    fake = ReadonlyFake()

    def fail():
        raise RuntimeError("secret=old-observer")

    fake.namespace_metadata = fail
    result = fake.run()
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "HOST"
    assert "diagnostic_code" not in result


def test_successor_registration_is_current_without_execute_or_host_invocation(
    monkeypatch,
):
    specs = runner._checkpoint_specs()
    spec = specs[diagnostic.CHECKPOINT]
    assert spec.remote_branch == diagnostic.BRANCH
    assert spec.preflight is runner._arch134_readonly_diagnostic_preflight
    assert spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(specs, diagnostic.BRANCH, "push")
        == diagnostic.CHECKPOINT
    )
    assert (
        runner.resolve_ci_checkpoint(specs, readonly.BRANCH, "push")
        == readonly.CHECKPOINT
    )
    assert runner.CI_CERTIFICATION_PROFILES[diagnostic.CHECKPOINT] == "robinhood"
    assert diagnostic.CHECKPOINT not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert readonly.CHECKPOINT not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    monkeypatch.setattr(
        "trading_bot.supervised_release.deployment_admission_diagnostic_host.preflight",
        lambda: pytest.fail("source tests must not invoke the real host observer"),
    )
    assert (
        runner._arch134_readonly_diagnostic_authority_check(
            runner.Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )


def test_r3n_prepublication_admission_dispatches_current_successor_authority(
    monkeypatch, tmp_path
):
    captured: dict[str, object] = {}

    def verify(spec, **kwargs):
        captured["spec"] = spec
        captured["kwargs"] = kwargs
        return True, tmp_path / "report.json"

    monkeypatch.setattr(
        runner,
        "_prepublication_source",
        lambda _: runner.PrepublicationSource(
            {}, "b" * 40, "c" * 40, ("scripts/checkpoint_runner.py",), "FULL", ()
        ),
    )
    monkeypatch.setattr(runner, "verify_checkpoint", verify)
    result = runner.prepublication_admission(
        repo_root=tmp_path,
        evidence_root=tmp_path / "evidence",
    )

    assert result == (True, tmp_path / "report.json")
    spec = captured["spec"]
    assert spec.authority_check is runner._arch134_r3n_prepublication_authority_check
    assert captured["kwargs"] == {
        "repo_root": tmp_path,
        "evidence_root": tmp_path / "evidence",
    }


@pytest.mark.parametrize("identity_bad", [True, False])
def test_general_admission_preserves_identity_and_both_context_failures(
    monkeypatch, tmp_path, identity_bad
):
    from scripts.current_source_authority import AuthorityResult, PublicationContext

    monkeypatch.setattr(
        runner,
        "_arch132_r3n_admission_authority_check",
        lambda _: ("identity rejected",) if identity_bad else (),
    )
    calls = []

    def evaluate(root, *, publication_context):
        calls.append(publication_context)
        return AuthorityResult(
            publication_context,
            "a" * 40,
            "b" * 40,
            ("example",),
            ("semantic rejected",),
        )

    monkeypatch.setattr(runner, "evaluate_source_authority", evaluate)
    failures = runner._arch134_r3n_prepublication_authority_check(tmp_path)
    if identity_bad:
        assert failures == ("identity rejected",)
        assert calls == []
    else:
        assert failures == (
            "FEATURE: semantic rejected",
            "PROSPECTIVE_DEVELOP: semantic rejected",
        )
        assert calls == list(PublicationContext)


def test_diagnostic_overlay_preserves_frozen_r3m_and_reconstructs_exact_successor():
    assert runner.ARCH132_R3M_AST_PINS["_batch_workflow_is_reviewed"] == (
        "3f910a44262aa76ee52b25158492a3b4061b1d0274414d8c2fb850725091c87d"
    )
    assert runner.ARCH132_R3M_MAPS_SHA256 == (
        "4da47bfe990ae9270415a54ee63af0896d0888a9bdef25124745491c7f1e10c6"
    )
    for ast_pin, before, after in (
        (
            True,
            runner.ARCH134_READONLY_DIAGNOSTIC_AST_PREDECESSORS,
            runner.ARCH134_READONLY_DIAGNOSTIC_AST_PINS,
        ),
        (
            False,
            runner.ARCH134_READONLY_DIAGNOSTIC_BLOB_PREDECESSORS,
            runner.ARCH134_READONLY_DIAGNOSTIC_BLOB_PINS,
        ),
    ):
        for key, predecessor in before.items():
            assert (
                runner._arch134_readonly_diagnostic_pin(
                    key, predecessor, ast_pin=ast_pin
                )
                == after[key]
            )
            with pytest.raises(ValueError):
                runner._arch134_readonly_diagnostic_pin(
                    key, "0" * len(predecessor), ast_pin=ast_pin
                )


def test_diagnostic_overlay_bypass_and_unrelated_workflow_drift_fail_closed(
    monkeypatch,
):
    root = runner.Path(runner.__file__).resolve().parents[1]
    monkeypatch.setattr(runner, "ARCH134_READONLY_DIAGNOSTIC_BLOB_PINS", {})
    assert runner._arch134_readonly_diagnostic_authority_check(root)

    # Current workflow drift is owned by the current semantic predicate.
    monkeypatch.undo()
    monkeypatch.setattr(
        runner, "_arch134_current_batch_workflow_is_reviewed", lambda _: False
    )
    assert runner._arch134_readonly_diagnostic_authority_check(root)


def test_diagnostic_successor_routes_shared_and_direct_overlay_endpoints(
    monkeypatch,
):
    root = runner.Path(runner.__file__).resolve().parents[1]
    previous_overlay = runner._ARCH134_READONLY_DIAGNOSTIC_PREVIOUS_OVERLAY
    assert runner._arch146a_overlay is previous_overlay
    assert (
        runner._arch134_d1s3_shared_successor_pin
        is runner._ARCH134_READONLY_DIAGNOSTIC_PREVIOUS_SHARED_SUCCESSOR_PIN
    )
    for relative, pin in runner.ARCH134_READONLY_DIAGNOSTIC_SHARED_BLOB_PINS.items():
        assert runner._arch134_readonly_diagnostic_shared_successor_pin(relative) == pin
    relative = "docs/AI_DEVELOPMENT_WORKFLOW.md"
    assert (
        runner._arch134_readonly_diagnostic_overlay(
            relative, runner.ARCH132_R3M_BLOB_PINS[relative], ast_pin=False
        )
        == runner.ARCH134_READONLY_DIAGNOSTIC_BLOB_PINS[relative]
    )
    relative = (
        "tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py"
    )
    assert (
        runner._arch134_readonly_diagnostic_pin(
            relative,
            runner.ARCH134_READONLY_DIAGNOSTIC_BLOB_PREDECESSORS[relative],
            ast_pin=False,
        )
        == runner.ARCH134_READONLY_DIAGNOSTIC_BLOB_PINS[relative]
    )
    calls: list[str] = []
    shared_calls: list[str] = []
    original_overlay = runner._arch134_readonly_diagnostic_overlay
    original_shared = runner._arch134_readonly_diagnostic_shared_successor_pin

    def traced_overlay(key, predecessor, *, ast_pin):
        calls.append(key)
        return original_overlay(key, predecessor, ast_pin=ast_pin)

    def traced_shared(relative):
        shared_calls.append(relative)
        return original_shared(relative)

    monkeypatch.setattr(runner, "_arch134_readonly_diagnostic_overlay", traced_overlay)
    monkeypatch.setattr(
        runner, "_arch134_readonly_diagnostic_shared_successor_pin", traced_shared
    )
    assert runner._arch134_readonly_diagnostic_authority_check(root) == ()
    assert calls or shared_calls
    assert runner._arch146a_overlay is previous_overlay
    assert (
        runner._arch134_d1s3_shared_successor_pin
        is runner._ARCH134_READONLY_DIAGNOSTIC_PREVIOUS_SHARED_SUCCESSOR_PIN
    )


def test_diagnostic_current_authority_does_not_rebind_historical_entrypoints():
    root = runner.Path(runner.__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    assert runner._arch134_readonly_diagnostic_authority_check(root) == ()
    assert runner._batch_workflow_is_reviewed(workflow)
    assert not runner._ARCH132_R3M_PREDECESSOR_BATCH_WORKFLOW_IS_REVIEWED(workflow)
    historical_workflow = workflow.replace(
        runner.ARCH134_READONLY_DIAGNOSTIC_R1_NAME,
        runner.ACTIVE_CI_CHECKPOINTS[0],
        1,
    )
    assert runner._ARCH132_R3M_PREDECESSOR_BATCH_WORKFLOW_IS_REVIEWED(
        historical_workflow
    )
    assert (
        runner._ARCH134_READONLY_DIAGNOSTIC_PREVIOUS_OVERLAY
        is not runner._arch134_readonly_diagnostic_overlay
    )
    assert (
        runner._ARCH134_READONLY_DIAGNOSTIC_PREVIOUS_SHARED_SUCCESSOR_PIN
        is not runner._arch134_readonly_diagnostic_shared_successor_pin
    )
    assert runner._arch132_r3m_authority_check(root) == ()
    assert runner._arch132_r3n_c4_authority_check(root) == ()
    assert runner._readonly_candidate_authority_check(root) == ()
    assert (
        runner._arch134_d1s3_shared_successor_pin(
            "tests/runtime/checkpoint_runner/test_ci.py"
        )
        == runner.READONLY_BLOB_AFTER["tests/runtime/checkpoint_runner/test_ci.py"]
    )
