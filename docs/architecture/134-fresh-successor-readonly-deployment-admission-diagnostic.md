# Architecture 134 — Fresh-Successor READ-ONLY Deployment-Admission Diagnostic

## Scope

This checkpoint is a source-only successor to the accepted v1 read-only
deployment-admission observer. It adds a closed diagnostic taxonomy while
preserving the v1 coarse `BLOCKED / HOST` contract and all production-boundary
semantics.

The exact reviewed base is:

    origin/develop HEAD 8a6791ba036a60f978d700bba0a2f1bc65a631bc
    tree 80ebe3d10cdbb63828f08fe0909079c5aaefb8d6

The successor checkpoint is
`arch134-fresh-successor-readonly-deployment-admission-diagnostic` on
`feature/robinhood-production-paper-fresh-successor-readonly-deployment-admission-diagnostic-current`.
It is read-only, has `execute = None`, and is mapped to canonical ROBINHOOD
certification.

## Diagnostic contract

The successor preserves `reason = HOST` and adds one validated closed
`diagnostic_code`. The reviewed codes are:

- `HOST_SESSION`
- `HOST_PARENT`
- `HOST_ANCESTORS`
- `HOST_NAMESPACE_COLLECTION`
- `HOST_NAMESPACE_POLICY`
- `HOST_FORBIDDEN_IDENTITY`
- `HOST_SECURITY_COLLECTION`
- `HOST_TOKEN_POLICY`
- `HOST_SACL_POLICY`
- `HOST_RUNTIME_PYTHON_IDENTITY`
- `HOST_QUIESCENCE_COLLECTION`
- `HOST_QUIESCENCE_POLICY`
- `HOST_UNKNOWN`

Unknown exceptions are sanitized to `HOST_UNKNOWN`; raw exception text,
Win32/native values and secret fixture material are never serialized.
Blocked evidence has an exact bounded field set. Effect counters remain zero
and authority flags remain false. A PASS retains the existing
`READY_FOR_SUCCESSOR_ROOT_WRITE_AUTHORITY_AND_ACL_REVIEW` result and grants no
root creation, ACL/ownership mutation, release materialization,
scheduler/runtime binding, F1, provider, broker or live authority.

## Predecessor evidence

The first real-host v1 observer attempt remains immutable evidence and is not
rerun:

    source HEAD 8a6791ba036a60f978d700bba0a2f1bc65a631bc
    source tree 80ebe3d10cdbb63828f08fe0909079c5aaefb8d6
    report SHA256 3f412affd0fd89b850d4f2de4b7e27680b01780c9e1f6fdd3957a51821e23a36
    status BLOCKED
    reason HOST
    diagnostic_process_starts 23
    production effects NOT_RUN / all observer counters zero
    protected execution NOT_AUTHORIZED / all authority flags false

The precise v1 host subreason remains unknown by design.

## Current authority and reuse

The frozen R3M predecessor literals and byte reconstruction remain unchanged.
The diagnostic successor uses an additive exact-source overlay for the current
workflow and runner bytes. Removing or bypassing that overlay exposes the
predecessor workflow drift; unrelated workflow/source changes fail closed.
The overlay also records the correction for the real #738 mapped
certification metadata: `full-tests` is required to be completed with a
`skipped` conclusion and no steps. This preserves fail-closed repository,
workflow, event, SHA/tree, branch, profile, attempt, job, step and uniqueness
requirements.

The later #739 develop result safely fell back to broad tests with
`DEVELOP_CERTIFICATION_REUSE=False` and `provenance_not_proven`. That is a
throughput/workflow defect, not a reason to weaken admission. The correction is
batched into this same runner-touch checkpoint.

No host preflight, production namespace inspection, scheduler/security command,
successor release root, ACL change, provider/broker operation, live effect or
Architecture 146-B work is part of this checkpoint.
