from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.supervised_release import installation_reconciliation as subject
from trading_bot.supervised_release.installation_contract import InstalledEvidence


def _evidence(image_identity=(1855336320, 9001)):
    return InstalledEvidence(
        subject.EXPECTED_RELEASE_ID,
        subject.EXPECTED_MANIFEST_SHA256,
        subject.EXPECTED_BINDING_SHA256,
        subject.EXPECTED_PARENT_IDENTITY,
        image_identity,
        subject.EXPECTED_PYTHON_IDENTITY,
    )


def _frozen(monkeypatch):
    release = SimpleNamespace(
        manifest=SimpleNamespace(release_id=subject.EXPECTED_RELEASE_ID),
        expected_manifest_sha256=subject.EXPECTED_MANIFEST_SHA256,
    )
    binding = SimpleNamespace(sha256=subject.EXPECTED_BINDING_SHA256)
    paths = SimpleNamespace(
        final=subject.EXPECTED_FINAL,
        staging=subject.EXPECTED_STAGING,
    )
    monkeypatch.setattr(subject, "_attempt_context", lambda: None)
    monkeypatch.setattr(subject.ag, "_administrator_host", lambda: None)
    monkeypatch.setattr(subject, "_frozen_inputs", lambda: (release, binding, paths))
    return release, binding, paths


def test_attempt_context_requires_exact_consumed_latch_and_failed_report(
    tmp_path, monkeypatch
):
    attempt = tmp_path / "attempt.json"
    attempt.write_bytes(subject.ATTEMPT_BYTES)
    report = tmp_path / "report.json"
    state = {
        "head": subject.FAILED_AG_HEAD,
        "tree": subject.FAILED_AG_TREE,
        "branch": subject.FAILED_AG_BRANCH,
        "porcelain": "",
    }
    payload = {
        "schema": "ai-trading-bot-checkpoint-runner/v1",
        "kind": "protected_execution",
        "checkpoint": "arch133-robinhood-supervised-release-installation-operator",
        "status": "STOPPED",
        "source": {
            "before": state,
            "after": state,
            "remote_branch": subject.FAILED_AG_BRANCH,
            "remote_head": subject.FAILED_AG_HEAD,
            "identity_stable": True,
        },
        "result": {
            "status": "INDETERMINATE",
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "INDETERMINATE",
                "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
                "reason": "PUBLICATION",
            },
        },
        "effect_disposition": "MAY_HAVE_OCCURRED",
        "protected_execution": "ATTEMPTED",
        "automatic_retry": "NOT_AUTHORIZED",
    }
    report.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(subject, "ATTEMPT_PATH", attempt)
    monkeypatch.setattr(subject, "REPORT_PATH", report)

    subject._attempt_context()

    # checkpoint_runner writes the durable AG latch through Windows text mode,
    # therefore the exact persisted incident record terminates with CRLF.
    assert subject.ATTEMPT_BYTES.endswith(b"\r\n")
    attempt.write_bytes(subject.ATTEMPT_BYTES[:-2] + b"\n")
    with pytest.raises(ValueError):
        subject._attempt_context()
    attempt.write_bytes(subject.ATTEMPT_BYTES)

    payload["result"]["primary"]["reason"] = "FINAL_VERIFICATION"
    report.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        subject._attempt_context()


def test_frozen_inputs_require_exact_failed_ag_identity(monkeypatch):
    release = SimpleNamespace(
        manifest=SimpleNamespace(release_id=subject.EXPECTED_RELEASE_ID),
        expected_manifest_sha256=subject.EXPECTED_MANIFEST_SHA256,
    )
    binding = SimpleNamespace(sha256=subject.EXPECTED_BINDING_SHA256)
    paths = SimpleNamespace(
        final=subject.EXPECTED_FINAL,
        staging=subject.EXPECTED_STAGING,
    )
    values = {
        ("rev-parse", "HEAD"): subject.FAILED_AG_HEAD,
        ("rev-parse", "HEAD^{tree}"): subject.FAILED_AG_TREE,
        ("branch", "--show-current"): subject.FAILED_AG_BRANCH,
    }
    monkeypatch.setattr(subject.ag, "_git", lambda *args: values[args])
    monkeypatch.setattr(subject.ag, "_derive_release", lambda: (release, binding))
    monkeypatch.setattr(subject, "replay_inputs", lambda *args: paths)

    assert subject._frozen_inputs() == (release, binding, paths)

    values[("rev-parse", "HEAD")] = "0" * 40
    with pytest.raises(ValueError):
        subject._frozen_inputs()


def test_exact_final_only_reconciles_installed(monkeypatch):
    release, binding, _ = _frozen(monkeypatch)
    final = SimpleNamespace(identity=(1855336320, 9001))
    evidence = _evidence(final.identity)
    monkeypatch.setattr(subject, "_presence", lambda paths: (final, None))
    monkeypatch.setattr(
        subject,
        "observe_installed_release",
        lambda r, b, native: evidence,
    )
    monkeypatch.setattr(
        subject,
        "observe_staging_release",
        lambda *args, **kwargs: pytest.fail("staging observer must not run"),
    )

    result = subject._preflight()

    assert result["status"] == "PASS"
    assert result["effect_disposition"] == "CONFIRMED"
    assert result["primary"]["status"] == "FINAL_INSTALLED_VERIFIED"
    assert result["primary"]["disposition"] == "RECONCILED_INSTALLED"
    assert result["primary"]["image_identity"] == final.identity
    assert release is not None and binding is not None


def test_exact_staging_only_is_preserved_and_never_promoted(monkeypatch):
    _frozen(monkeypatch)
    staging = SimpleNamespace(identity=(1855336320, 9002))
    evidence = _evidence(staging.identity)
    monkeypatch.setattr(subject, "_presence", lambda paths: (None, staging))
    monkeypatch.setattr(
        subject,
        "observe_staging_release",
        lambda r, b, native: evidence,
    )
    monkeypatch.setattr(
        subject,
        "observe_installed_release",
        lambda *args, **kwargs: pytest.fail("final observer must not run"),
    )

    result = subject._preflight()

    assert result["status"] == "PASS"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["primary"]["status"] == "STAGING_VERIFIED_PRESERVED"
    assert result["primary"]["disposition"] == "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY"


@pytest.mark.parametrize(
    ("presence", "reason"),
    [
        ((None, None), "FINAL_AND_STAGING_BOTH_ABSENT"),
        (
            (
                SimpleNamespace(identity=(1, 1)),
                SimpleNamespace(identity=(1, 2)),
            ),
            "FINAL_AND_STAGING_BOTH_PRESENT",
        ),
    ],
)
def test_mixed_or_missing_namespace_remains_blocked(monkeypatch, presence, reason):
    _frozen(monkeypatch)
    monkeypatch.setattr(subject, "_presence", lambda paths: presence)

    result = subject._preflight()

    assert result["status"] == "BLOCKED"
    assert result["primary"]["status"] == "RECONCILIATION_UNRESOLVED"
    assert result["primary"]["reason"] == reason


def test_presence_drift_blocks_without_observer(monkeypatch):
    _frozen(monkeypatch)
    observations = iter(
        [
            (SimpleNamespace(identity=(1, 1)), None),
            (None, SimpleNamespace(identity=(1, 2))),
        ]
    )
    monkeypatch.setattr(subject, "_presence", lambda paths: next(observations))
    monkeypatch.setattr(
        subject,
        "observe_installed_release",
        lambda *args, **kwargs: pytest.fail("observer must not run"),
    )
    monkeypatch.setattr(
        subject,
        "observe_staging_release",
        lambda *args, **kwargs: pytest.fail("observer must not run"),
    )

    result = subject._preflight()

    assert result["status"] == "BLOCKED"
    assert result["primary"]["reason"] == "PRESERVED_NAMESPACE_DRIFT"


def test_observer_or_evidence_failure_is_sanitized(monkeypatch):
    _frozen(monkeypatch)
    final = SimpleNamespace(identity=(1855336320, 9001))
    monkeypatch.setattr(subject, "_presence", lambda paths: (final, None))
    monkeypatch.setattr(
        subject,
        "observe_installed_release",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("private")),
    )

    result = subject._preflight()

    assert result == {
        "status": "BLOCKED",
        "effect_disposition": "MAY_HAVE_OCCURRED",
        "automatic_retry": "NOT_AUTHORIZED",
        "primary": {
            "status": "RECONCILIATION_UNRESOLVED",
            "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
            "reason": "RECONCILIATION_OBSERVATION_REJECTED",
        },
    }


def test_fixed_paths_are_incident_specific():
    assert subject.ATTEMPT_PATH == Path(
        r"F:\AI\temp\arch133-ag-installation-attempt\attempt.json"
    )
    assert subject.REPORT_PATH.name == "report.json"
    assert "execute-20261011T034428.605950Z" in str(subject.REPORT_PATH)


def test_checkpoint_registration_is_read_only():
    name = "arch133-robinhood-supervised-release-installation-reconciliation"
    spec = runner._checkpoint_specs()[name]

    assert runner.ACTIVE_CI_CHECKPOINTS[:2] == (
        "arch134-f1r1-d1s3-successor-release-installation-operator",
        "arch133-robinhood-supervised-release-installation-operator",
    )
    assert name not in runner.ACTIVE_CI_CHECKPOINTS
    assert spec.preflight is runner._supervised_installation_reconciliation_preflight
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert (
        spec.remote_branch
        == "feature/robinhood-supervised-release-installation-reconciliation"
    )
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._supervised_installation_reconciliation_authority_check(root) == ()


def test_incident_record_drift_is_rejected(monkeypatch):
    reads = iter((subject.ATTEMPT_BYTES, b"changed"))
    monkeypatch.setattr(subject, "_read_record", lambda path, limit: next(reads))

    with pytest.raises(ValueError):
        subject._attempt_context()


def test_late_namespace_drift_blocks_after_exact_final_replays(monkeypatch):
    _frozen(monkeypatch)
    final = SimpleNamespace(identity=(1855336320, 9001))
    evidence = _evidence(final.identity)
    observations = iter(((final, None), (final, None), (None, None)))
    monkeypatch.setattr(subject, "_presence", lambda paths: next(observations))
    monkeypatch.setattr(
        subject,
        "observe_installed_release",
        lambda r, b, native: evidence,
    )

    result = subject._preflight()

    assert result["status"] == "BLOCKED"
    assert result["primary"]["reason"] == "PRESERVED_NAMESPACE_DRIFT"
