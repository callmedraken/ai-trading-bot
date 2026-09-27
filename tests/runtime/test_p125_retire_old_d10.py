"""Source-only operator tests; no protected Windows operation is called."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import d10_protected_replacement as r
from scripts import p125_retire_old_d10 as op


class FakeOperations:
    def __init__(self, state: r.CleanupState, post: bool = True):
        self.state = state
        self.post = post
        self.post_calls = 0

    def begin_fixed_retired_cleanup_session(self):
        return SimpleNamespace(state=self.state), None

    def observe_retired_cleanup_post(self) -> bool:
        self.post_calls += 1
        return self.post


@pytest.mark.parametrize(
    "state,reason",
    [
        (
            r.CleanupState.PARTIAL_RETIRED,
            r.CleanupBlockReason.SEPARATE_RECOVERY_REQUIRED,
        ),
        (r.CleanupState.CONFLICTING, r.CleanupBlockReason.NAMESPACE_CONFLICT),
    ],
)
def test_no_mutation_for_partial_or_conflicting(
    state: r.CleanupState, reason: r.CleanupBlockReason
) -> None:
    operations = FakeOperations(state)
    result = op.run_cleanup(operations)
    assert result.phase is r.CleanupPhase.BLOCKED
    assert result.reason_code is reason
    assert operations.post_calls == 0


def test_absent_idempotent_pass_needs_fresh_post_proof() -> None:
    operations = FakeOperations(r.CleanupState.RETIRED_ABSENT)
    result = op.run_cleanup(operations)
    assert result.phase is r.CleanupPhase.PASS
    assert operations.post_calls == 1
    transcript = json.loads(result.canonical_transcript())
    assert transcript["activation_authority"] == "NONE"
    assert transcript["scheduler_authority"] == "NONE"
    assert transcript["trading_authority"] == "NONE"
    operations.post = False
    assert (
        op.run_cleanup(operations).reason_code
        is r.CleanupBlockReason.POST_CLEANUP_VERIFICATION_FAILED
    )


def test_operator_import_and_cli_are_inert_without_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Path(op.__file__).read_text(encoding="utf-8")
    assert "DeleteFileW" not in source
    assert "RemoveDirectoryW" not in source
    assert list(inspect.signature(op.run_cleanup).parameters) == ["operations"]
    with pytest.raises(SystemExit):
        op.main([])
    assert "protected cleanup flag" in capsys.readouterr().err
