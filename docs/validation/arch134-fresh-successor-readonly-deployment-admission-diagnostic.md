# Architecture 134 Diagnostic Successor Validation

## Source boundary

The implementation is based on `origin/develop` HEAD
`8a6791ba036a60f978d700bba0a2f1bc65a631bc` with tree
`80ebe3d10cdbb63828f08fe0909079c5aaefb8d6`. It uses the exact successor
branch `feature/robinhood-production-paper-fresh-successor-readonly-deployment-admission-diagnostic-current`.

The v1 observer remains a separate predecessor contract. Its first real-host
attempt is preserved as BLOCKED/HOST with report SHA256
`3f412affd0fd89b850d4f2de4b7e27680b01780c9e1f6fdd3957a51821e23a36`,
`diagnostic_process_starts = 23`, zero production effects and no protected
authority. It is not rerun.

## Focused validation

The successor tests use only fakes and disposable values. They cover read-session,
parent, ancestor-policy, namespace, forbidden-identity, security, token,
privilege, SACL, runtime/Python identity, quiescence and unknown-host failure
boundaries. Every blocked result is checked for sanitized canonical bounded
evidence, zero effects, false authority, and rejection of malformed or extra
diagnostic fields. The predecessor observer is checked to remain coarse
`BLOCKED / HOST` without a diagnostic code.

The runner tests cover the exact #738 mapped metadata, including the skipped
`full-tests` job, and reject attempt mismatches, wrong repository/workflow/
event/SHA/tree/branch/profile, wrong job/step state, unexpected full execution,
duplicates and truncated metadata. Broad-route authority remains fail-closed.

The additive diagnostic overlay proves that the frozen R3M predecessor literal
and reconstruction remain unchanged, that the exact current workflow bytes are
accepted only through the overlay, that bypass/removal exposes predecessor
drift, and that unrelated workflow changes are rejected.

## Explicit non-scope

No real host observer, Windows scheduler/security command, production release
namespace, ACL, root, runtime binding, provider, broker, live or Architecture
146-B operation is executed. Canonical ROBINHOOD certification is owned by
GitHub after publication; local verification is limited to focused tests,
Ruff checks and `git diff --check`.
