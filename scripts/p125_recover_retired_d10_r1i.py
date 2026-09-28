"""Explicit protected P125-R1I retired S5-R8 recovery; inert at import."""

from __future__ import annotations

import argparse
import sys
from typing import Protocol

from scripts import d10_protected_replacement as replacement
from scripts.p125_retire_old_d10 import CleanupSession


class RecoveryOperations(Protocol):
    def begin_fixed_retired_recovery_session(
        self,
    ) -> tuple[object, CleanupSession | None]: ...

    def observe_retired_cleanup_post(self) -> bool: ...


def _blocked(
    state: replacement.CleanupState,
    reason: replacement.CleanupBlockReason,
    completed: int = 0,
    diagnostic: replacement.DeleteDiagnostic | None = None,
) -> replacement.CleanupResult:
    return replacement.CleanupResult(
        replacement.CleanupPhase.BLOCKED,
        state,
        completed,
        reason,
        diagnostic,
        replacement.CleanupOperation.R1I,
    )


def run_recovery(operations: RecoveryOperations) -> replacement.CleanupResult:
    """Consume only the exact incident admission; start at original index one."""
    state = replacement.CleanupState.CONFLICTING
    try:
        observation, session = operations.begin_fixed_retired_recovery_session()
        state = observation.state
        if type(state) is not replacement.CleanupState:
            raise ValueError("recovery state unreviewed")
        if state is not replacement.CleanupState.PARTIAL_RETIRED:
            return _blocked(state, replacement.CleanupBlockReason.ADMISSION_FAILED)
        replacement.require_retired_recovery_plan(observation.plan)
        if (
            observation.missing_indices != (0,)
            or session is None
            or session.plan != observation.plan
            or type(session.completed_targets) is not int
            or session.completed_targets != replacement.R1I_MISSING_PREFIX_COUNT
        ):
            raise ValueError("recovery session not admitted")
    except Exception:
        return _blocked(
            replacement.CleanupState.CONFLICTING,
            replacement.CleanupBlockReason.ADMISSION_FAILED,
        )
    while session.completed_targets < replacement.R1I_PLAN_TARGET_COUNT:
        before = session.completed_targets
        try:
            outcome = session.delete_next()
        except Exception:
            outcome = replacement.MutationOutcome.INDETERMINATE
        if (
            outcome is not replacement.MutationOutcome.SUCCESS
            or type(session.completed_targets) is not int
            or session.completed_targets != before + 1
        ):
            diagnostic = getattr(session, "delete_diagnostic", None)
            if (
                type(diagnostic) is not replacement.DeleteDiagnostic
                or diagnostic.target_index != before
            ):
                diagnostic = replacement.DeleteDiagnostic(
                    before, replacement.DeleteFailureStage.PRE_CALL
                )
            return _blocked(
                state,
                replacement.CleanupBlockReason.INDETERMINATE_DELETE,
                before,
                diagnostic,
            )
    try:
        if operations.observe_retired_cleanup_post() is True:
            return replacement.CleanupResult(
                replacement.CleanupPhase.PASS,
                replacement.CleanupState.RETIRED_ABSENT,
                session.completed_targets,
                operation=replacement.CleanupOperation.R1I,
            )
    except Exception:
        pass
    return _blocked(
        state,
        replacement.CleanupBlockReason.POST_CLEANUP_VERIFICATION_FAILED,
        session.completed_targets,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--execute-protected-p125-r1i-retired-recovery",
        action="store_true",
        help="explicitly run Administrator-only incident-specific retired recovery",
    )
    arguments = parser.parse_args(argv)
    if not arguments.execute_protected_p125_r1i_retired_recovery:
        parser.error("P125-R1I remains inert without the exact protected recovery flag")
    from scripts import d10_protected_replacement_windows as windows

    try:
        result = run_recovery(windows)
    except Exception:
        result = _blocked(
            replacement.CleanupState.CONFLICTING,
            replacement.CleanupBlockReason.ADMISSION_FAILED,
        )
    sys.stdout.buffer.write(result.canonical_transcript())
    return 0 if result.phase is replacement.CleanupPhase.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
