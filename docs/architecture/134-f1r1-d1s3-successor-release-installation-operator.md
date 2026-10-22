# Architecture 134-F1R1-D1S3 — successor release installation operator

## Status and boundary

This document defines the source-only checkpoint
`arch134-f1r1-d1s3-successor-release-installation-operator`. D1S2 is SOURCE
ACCEPTED and integrated at HEAD
`2b697b79e6bdbc964d2b0414ced057628e6c2da7`, tree
`e510210070874ade43a240457645939650e457d8`. D1S3 feature CI is
`39767775803` attempt 1 SUCCESS; preserved failed run `39765888238` attempt 1;
post-merge develop CI `39839904057` attempt 1 SUCCESS.

This layer supplies source for a later separately reviewed protected
installation/readiness dispatch. The source checkpoint performs no production
installation or publication, does not create the successor root, and never
reads credentials or contacts providers, paper, broker, D1, D2, Scheduler, or
live surfaces. The historical Architecture-133 AG installation operator is
not repurposed or mutated.

## Source and release identity

The protected dispatch admits only the exact remote
`https://github.com/callmedraken/ai-trading-bot.git`, exact D1S3 branch/ref,
live remote HEAD, local HEAD/tree, clean index/worktree, exact origin URL, and
complete source inventory. The accepted HEAD and tree are supplied through
reviewed environment interlocks at the later protected boundary; no future
commit SHA is guessed or derived from installed bytes. The complete release
is collected through the accepted Architecture-133 collector, replayed through
`VerifiedRelease`, and joined to a canonical `RuntimeBinding`.

Only `F:\AITradingBot\releases\<release-id>` and
`F:\AITradingBot\runtime\python.exe` are production paths. Runtime invocation
remains `-I -S -B`; a mutable checkout cannot satisfy installed-runtime
admission.

## Read-only preflight and one-shot installation

Preflight observes the exact FINAL and sibling `.installing` paths and returns
closed source, release, manifest, inventory, binding, root, attempt, and zero
effect evidence. `INSTALL_REQUIRED` is eligible only when FINAL and staging
are absent, the fresh D1S3 attempt is available, source/host prerequisites and
the exact release declaration pass, and all protected counters are zero.
`ALREADY_INSTALLED_EXACT` never enters execute. Conflicts are `BLOCKED` or
`INDETERMINATE` and are never repaired or retried.

The fixed D1S3 attempt namespace is
`F:\AI\temp\arch134-f1r1-d1s3-installation-attempt\attempt.json`. Preflight
never creates it. A later protected execute reserves it exclusively, writes,
flushes, fsyncs, and reads it back before entering the accepted
Architecture-133 installer exactly once. The latch is never deleted, reset,
rewritten, or treated as retry authority. Any exception or KeyboardInterrupt
after entry is consumed `INDETERMINATE`; separate read-only reconciliation is
required.

## Installation and successor-root boundary

The only effect permitted to the future protected execute is immutable release
installation through the accepted Architecture-133 engine. The result must
ACK the exact release, manifest, binding, and image identities, and the final
release is independently re-observed after installation. Scheduler/service/
boot/logon/startup behavior and all trading/provider/paper effects remain
outside this operator.

The frozen future root is
`F:\AITradingBot\Arch133\arch134-f1r1-d1-successor-soak-v1`. D1S3 observes it
only. If absent after a verified install, the closed result is
`READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW`; it is never provisioned
implicitly. `EMPTY_FRESH_ADMITTED` and `ALREADY_BOUND_EXACT` may proceed only
through the accepted D1S2 read-only composition. Conflicting, malformed,
consumed, aliased, reparse, wrong-policy, replaced, or indeterminate roots
stop. Original F1 and C2 evidence cannot substitute.

The lifecycle remains `RUNNING -> STOPPED -> optional read-only
reconciliation -> explicit manual start -> fresh admission -> RUNNING`.

## Mutable current-document policy

The current coordination documents `docs/PROJECT_STATUS.md` and
`docs/AI_TRADING_BOT_HANDOFF.md` are the only mutable current-state exception.
They are not executable blob authority under the D1S3 overlay. All executable
source, workflow, tests, AST functions, inventories, architecture documents,
validation documents, and every other pinned path remain exact and fail
closed. Removing the D1S3 overlay restores D1S2 exact-pin behavior.

Original F1 remains FINAL / INDETERMINATE / CONSUMED; C2 remains consumed and
non-reusable; Architecture 145 remains separate/offline; and live remains
NO-GO.

Also remove or update any tests and docs that referenced the old behavior.
