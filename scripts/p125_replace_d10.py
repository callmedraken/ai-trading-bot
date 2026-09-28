"""Explicit protected P125-R1 D10 replacement operator; inert at import."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Protocol

from scripts import d10_protected_replacement as replacement


class ReplacementSession(Protocol):
    result: replacement.ReplacementResult
    admission: object

    def retire_old_root(self) -> replacement.MutationOutcome: ...

    def publish_staged_root(self) -> replacement.MutationOutcome: ...


class RenameOperations(Protocol):
    def observe_namespace(self) -> replacement.NamespaceObservation: ...

    def begin_fixed_rename_session(self) -> ReplacementSession: ...

    def observe_post_publication(
        self, admission: object
    ) -> tuple[replacement.NamespaceObservation, replacement.PostPublicationFacts]: ...


class ReplacementOperations(RenameOperations, Protocol):
    def construct_fixed_staging(self, repository_root: Path) -> None: ...


def _classify_after_failure(
    operations: RenameOperations,
) -> replacement.NamespaceState:
    try:
        return replacement.classify_namespace(operations.observe_namespace())
    except Exception:
        return replacement.NamespaceState.CONFLICTING


def _blocked_before_admission(
    state: replacement.NamespaceState,
) -> replacement.ReplacementResult:
    if state in (
        replacement.NamespaceState.OLD_RETIRED,
        replacement.NamespaceState.NEW_CANONICAL,
    ):
        reason = replacement.BlockReason.SEPARATE_RECOVERY_REQUIRED
    elif state is replacement.NamespaceState.CONFLICTING:
        reason = replacement.BlockReason.NAMESPACE_CONFLICT
    else:
        reason = replacement.BlockReason.ADMISSION_FAILED
    return replacement.ReplacementResult(
        replacement.Phase.BLOCKED, state, reason_code=reason
    )


def run_replacement(
    repository_root: Path, operations: ReplacementOperations
) -> replacement.ReplacementResult:
    """Orchestrate one replacement attempt through the fixed Windows adapter."""
    try:
        initial = replacement.classify_namespace(operations.observe_namespace())
    except Exception:
        initial = replacement.NamespaceState.CONFLICTING
    if initial is replacement.NamespaceState.OLD_CANONICAL:
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            initial,
            reason_code=replacement.BlockReason.SEPARATE_RECOVERY_REQUIRED,
        )
    if initial in (
        replacement.NamespaceState.OLD_RETIRED,
        replacement.NamespaceState.NEW_CANONICAL,
        replacement.NamespaceState.CONFLICTING,
    ):
        return _blocked_before_admission(initial)

    if initial is replacement.NamespaceState.CLEAN_INITIAL:
        try:
            operations.construct_fixed_staging(repository_root)
        except Exception:
            after_staging_failure = _classify_after_failure(operations)
            if after_staging_failure in (
                replacement.NamespaceState.OLD_RETIRED,
                replacement.NamespaceState.NEW_CANONICAL,
            ):
                return _blocked_before_admission(after_staging_failure)
            return replacement.ReplacementResult(
                replacement.Phase.BLOCKED,
                after_staging_failure,
                reason_code=replacement.BlockReason.STAGING_FAILED,
            )

    return run_admitted_replacement(operations)


def run_admitted_replacement(
    operations: RenameOperations,
) -> replacement.ReplacementResult:
    """After entry admission, perform the existing fixed one-invocation sequence."""
    try:
        session = operations.begin_fixed_rename_session()
    except Exception:
        after_admission_failure = _classify_after_failure(operations)
        return _blocked_before_admission(after_admission_failure)

    try:
        first_outcome = session.retire_old_root()
    except Exception:
        _classify_after_failure(operations)
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.OLD_CANONICAL,
            reason_code=replacement.BlockReason.INDETERMINATE_MUTATION,
        )
    if first_outcome is not replacement.MutationOutcome.SUCCESS:
        # Fresh classification is read-only evidence, never permission to advance.
        # Preserve the highest definitely completed state from this invocation.
        _classify_after_failure(operations)
        return session.result
    if session.result.phase is not replacement.Phase.READY_TO_PUBLISH_NEW:
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.OLD_RETIRED,
            (replacement.RenameStep.OLD_TO_RETIRED,),
            replacement.BlockReason.INVALID_TRANSITION,
        )

    try:
        second_outcome = session.publish_staged_root()
    except Exception:
        _classify_after_failure(operations)
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.OLD_RETIRED,
            (replacement.RenameStep.OLD_TO_RETIRED,),
            replacement.BlockReason.INDETERMINATE_MUTATION,
        )
    if second_outcome is not replacement.MutationOutcome.SUCCESS:
        _classify_after_failure(operations)
        return session.result
    if session.result.phase is not replacement.Phase.VERIFY_PUBLICATION:
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.NEW_CANONICAL,
            (
                replacement.RenameStep.OLD_TO_RETIRED,
                replacement.RenameStep.STAGING_TO_CANONICAL,
            ),
            replacement.BlockReason.INVALID_TRANSITION,
        )

    try:
        namespace, facts = operations.observe_post_publication(session.admission)
    except Exception:
        namespace = None
        facts = replacement.PostPublicationFacts(
            new_canonical_exact=False,
            staging_absent=False,
            old_retired_exact=False,
            canonical_trust_absent=False,
            activation_and_cache_absent=False,
            d5_capture_only_scheduler_exact=False,
            protected_parent_exact=False,
            same_local_ntfs_volume=False,
            unexpected_reserved_names_absent=False,
        )
    return replacement.verify_publication(session.result, namespace, facts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument(
        "--execute-protected-p125-r1",
        action="store_true",
        help="explicitly run the Administrator-only protected replacement",
    )
    arguments = parser.parse_args(argv)
    if not arguments.execute_protected_p125_r1:
        parser.error("P125-R1 remains inert without --execute-protected-p125-r1")

    from scripts import d10_protected_replacement_windows as windows

    try:
        result = run_replacement(arguments.repository_root, windows)
    except Exception:
        result = replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.CONFLICTING,
            reason_code=replacement.BlockReason.NAMESPACE_CONFLICT,
        )
    sys.stdout.buffer.write(result.canonical_transcript())
    return 0 if result.phase is replacement.Phase.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
