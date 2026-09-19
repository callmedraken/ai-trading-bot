# PD2D2-E2 Post-Mutation Reconciliation Validation Plan

## Scope

Validate the Architecture-108 zero-effect harness for the single successful
first Paper-v2 operation. This checkpoint adds only documentation, a new CLI,
a thin launcher, and focused source-only tests. Shared runtime and CLI source
remain unchanged.

## Source gates and provenance

Before review and after verification, confirm:

```text
branch: feature/personal-desktop-paper-runtime
starting HEAD: adb8884ca93f09f587e789bd00a960bcc335c809
starting tree: 1d812c901c8295eead43e93d0f0766b037cbb9e9
publication-freeze blob: b125cbb1c80a827f74018cf2955b9a27ba69fa90
production gate: false
recovery gate: false
supervised-execution gate: false
```

Any starting mismatch is a stop. No pull, reset, merge, rebase, amend, branch
switch, clean, discard, or self-correction is permitted.

## E2-A validation

- Genuine production composition obtains C1 before P2.
- P2 reads only frozen selected call #6 and reports no provider/database effect.
- GENESIS is reconstructed from C1/P2 and explicit `Decimal("25000")` before
  any account read.
- Independent GENESIS verification requires frozen ID/hash/length, timestamp,
  cash-only opening state, zero realized P&L, and empty metadata.
- The original verified prior comes from GENESIS-only full-lineage verification.
- Frozen F1/F2 inputs rebuild and detached-verify the exact 6199-byte plan.
- Request, plan, caller, selected snapshot, selection, and prior IDs are exact.

## E2-B validation

- Each genuine account read receives exactly
  `(exact_reconstructed_plan_bytes,)` as its historical configuration tuple.
- The validated account has one edge and exact ordered checkpoint IDs.
- Exactly one successor, report, selected snapshot dependency, and receipt
  exist.
- Strict parsers verify successor/report identities, sequence, prior,
  application, cycle result, and selected snapshot.
- The completed receipt matches the frozen operation, application, caller,
  request, original prior lineage, selected snapshot, and plan evidence.
- A second genuine read after inspection returns exactly equal evidence.

## E2-C validation

- Execution inputs use the installed verified receipt intent and application.
- The prior artifact lists are all empty and terminal bytes are reconstructed
  GENESIS bytes, proving the original operation—not a hypothetical successor.
- The fixed operation root is inspected once through the existing read-only
  inspector.
- Only exact `ALREADY_APPLIED/ALREADY_APPLIED` with frozen IDs and original
  GENESIS prior succeeds.
- `PENDING`, `BLOCKED`, `CONFLICTING`, any other diagnostic, or identity drift
  fails closed.
- Source contains no execution or receipt-recovery call.

## E2-D validation

- The parser has no positional or optional semantic fields.
- Any true effect gate blocks before construction or invocation of C1, P2,
  account reading, or inspection dependencies.
- Success emits one sanitized JSON record with schema
  `pd2d2-post-mutation-reconciliation-evidence/v1` and `RECONCILED`.
- Failure emits one sanitized nonzero record without exception text or raw
  evidence.
- The launcher uses the established repository `src` bootstrap and guarded
  `main` pattern.
- The disposable orchestration seam is one-shot and rejects genuine production
  callables.
## Focused commands

Run only the new harness tests and the smallest relevant existing read-authority
and inspection regressions. Use the worktree-bound `PYTHONPATH`, disable pytest's
cache provider, and run targeted Ruff check/format plus `git diff --check`.

Do not run the full repository suite and do not run the production launcher as
part of source verification.

## Acceptance evidence

Record exact focused test counts, Ruff and diff results, the three false gates,
unchanged publication-freeze blob, zero production effects, ending HEAD/tree,
exact staged filenames, commit/push range, and clean worktree status. Any
deviation remains unresolved until reviewed.
