"""Explicit protected P125-R1E retired S5-R8 cleanup operator; inert at import."""

from __future__ import annotations

import argparse
import sys
from typing import Protocol

from scripts import d10_protected_replacement as replacement


class CleanupSession(Protocol):
    plan: replacement.RetiredCleanupPlan
    completed_targets: int

    def delete_next(self) -> replacement.MutationOutcome: ...


class CleanupOperations(Protocol):
    def begin_fixed_retired_cleanup_session(
        self,
    ) -> tuple[object, CleanupSession | None]: ...

    def observe_retired_cleanup_post(self) -> bool: ...


def run_cleanup(operations: CleanupOperations) -> replacement.CleanupResult:
    """Run one frozen plan with no retry or caller-provided paths."""
    state = replacement.CleanupState.CONFLICTING
    try:
        observation, session = operations.begin_fixed_retired_cleanup_session()
        state = observation.state
        if type(state) is not replacement.CleanupState:
            raise ValueError("cleanup state unreviewed")
    except Exception:
        return replacement.CleanupResult(
            replacement.CleanupPhase.BLOCKED,
            replacement.CleanupState.CONFLICTING,
            reason_code=replacement.CleanupBlockReason.ADMISSION_FAILED,
        )
    if state is replacement.CleanupState.CONFLICTING:
        reason = replacement.CleanupBlockReason.NAMESPACE_CONFLICT
    elif state is replacement.CleanupState.PARTIAL_RETIRED:
        reason = replacement.CleanupBlockReason.SEPARATE_RECOVERY_REQUIRED
    elif state is replacement.CleanupState.RETIRED_ABSENT:
        try:
            if session is None and operations.observe_retired_cleanup_post() is True:
                return replacement.CleanupResult(replacement.CleanupPhase.PASS, state)
        except Exception:
            pass
        reason = replacement.CleanupBlockReason.POST_CLEANUP_VERIFICATION_FAILED
    else:
        if (
            session is None
            or type(session.plan) is not replacement.RetiredCleanupPlan
            or session.plan != observation.plan
            or len(session.plan.targets) > 4096
            or session.completed_targets != 0
        ):
            reason = replacement.CleanupBlockReason.ADMISSION_FAILED
        else:
            while session.completed_targets < len(session.plan.targets):
                before = session.completed_targets
                try:
                    outcome = session.delete_next()
                except Exception:
                    outcome = replacement.MutationOutcome.INDETERMINATE
                if (
                    outcome is not replacement.MutationOutcome.SUCCESS
                    or session.completed_targets != before + 1
                ):
                    return replacement.CleanupResult(
                        replacement.CleanupPhase.BLOCKED,
                        state,
                        before,
                        replacement.CleanupBlockReason.INDETERMINATE_DELETE,
                    )
            try:
                if operations.observe_retired_cleanup_post() is True:
                    return replacement.CleanupResult(
                        replacement.CleanupPhase.PASS,
                        replacement.CleanupState.RETIRED_ABSENT,
                        session.completed_targets,
                    )
            except Exception:
                pass
            return replacement.CleanupResult(
                replacement.CleanupPhase.BLOCKED,
                state,
                session.completed_targets,
                replacement.CleanupBlockReason.POST_CLEANUP_VERIFICATION_FAILED,
            )
    return replacement.CleanupResult(
        replacement.CleanupPhase.BLOCKED,
        state,
        reason_code=reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-protected-p125-r1e-cleanup",
        action="store_true",
        help="explicitly run Administrator-only retired deployment cleanup",
    )
    arguments = parser.parse_args(argv)
    if not arguments.execute_protected_p125_r1e_cleanup:
        parser.error("P125-R1E remains inert without the protected cleanup flag")
    from scripts import d10_protected_replacement_windows as windows

    try:
        result = run_cleanup(windows)
    except Exception:
        result = replacement.CleanupResult(
            replacement.CleanupPhase.BLOCKED,
            replacement.CleanupState.CONFLICTING,
            reason_code=replacement.CleanupBlockReason.ADMISSION_FAILED,
        )
    sys.stdout.buffer.write(result.canonical_transcript())
    return 0 if result.phase is replacement.CleanupPhase.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
