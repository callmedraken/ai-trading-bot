# Architecture 134-F1R1-D1S3 — successor release installation operator

## Status and boundary

This document defines the source-only checkpoint
`arch134-f1r1-d1s3-successor-release-installation-operator`. D1S2 is SOURCE
ACCEPTED and integrated at HEAD
`2b697b79e6bdbc964d2b0414ced057628e6c2da7`, tree
`e510210070874ade43a240457645939650e457d8`. D1S2 feature CI is
`39767775803` attempt 1 SUCCESS; preserved failed run `39765888238` attempt 1;
post-merge develop CI `39839904057` attempt 1 SUCCESS.

This layer supplies source for a later separately reviewed protected
installation/readiness dispatch. The source checkpoint performs no production
installation or publication, does not create the successor root, and never
reads credentials or contacts providers, paper, broker, D1, D2, Scheduler, or
live surfaces. The historical Architecture-133 AG installation operator is
not repurposed or mutated.

R4 integrates Administrator-before-latch recovery onto SOURCE/CERTIFICATION
ACCEPTED Architecture 132-R3K, HEAD
`5c57d49e31b1f0e5174bdc826b933118494e2456`, tree
`905c5a0006d0311b68d9a48947761b949bbcba5a`. R3 was CI-green but
source-rejected for Administrator-after-latch ordering; published R3J was
certification-rejected. Current ROBINHOOD uses accepted R3K four-lane timing
placement. D1S3 remains NOT SOURCE ACCEPTED pending R4 CI and ChatGPT review;
FULL remains pending and has not run. Develop remains accepted D1S2; protected
effects remain zero and live remains NO-GO.

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

R4 production execute ordering is accepted source identity -> exact
Administrator host admission through the existing `_administrator_host()` ->
read-only protected boundary construction -> authorization and read-only D1S3
preflight/eligibility -> durable latch consumption -> installer entry. A
non-Administrator rejection or boundary-construction failure is pre-entry and
cannot create or consume installation authority. Previously consumed or
ambiguous attempt evidence remains fail-closed; no reset or retry is granted.

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

## R3 native read-only composition

`_protected_boundary()` composes one exact `SuccessorReleaseDeclaration`,
`InstallationNativeObserver`, the accepted `WindowsObserver` image reader,
`NativeRuntimeObserver`, and `NativeSuccessorRootObserver`. Construction is
inert. Accepted-source HEAD/tree remain reviewed environment interlocks; R3
does not guess its future publication identity. Git's slash-form worktree
path is normalized before comparison with the fixed Windows worktree.

Installation observation reuses Architecture-133 no-follow read sessions,
parent policy and immutable-image replay, checks the pinned production Python
without executing it, and rechecks exact FINAL/staging absence or identity.
The original `ReleasePaths` installer grammar is unchanged. The separate
`D1S3ReadPaths` adapter grants only fixed production ancestors, the exact D1
root and three permitted filenames, and the fixed runtime subtree. It reuses
`WindowsReadSession` handle/ACL/namespace/byte primitives and exposes no writes.

Root facts are pinned and compared on repeated reads. Empty/absent roots are
observations only. Nonempty roots use the accepted `snapshot`/JSONL replay,
including lineage, fixed ordinals/dates, parent/grant prefixes, prior-child
progression, final cross-digests/counters, and actual installed image/Python/
store identities. Only an exact benign session-01 final before child-02 grant
is `ALREADY_BOUND_EXACT`; all-three filenames alone never suffice. Completed/
halted series are `CONSUMED`, not malformed. Invalid canonical evidence is
`MALFORMED`; unreadable/unprovable facts remain `INDETERMINATE`.

Active replay queries only its exact recorded PID/birth with read-only process
APIs. Definite exit/PID reuse/wrong executable is consumed. A different live
production PID is still unproven because its imports/substrate cannot be
admitted from a process handle. `ACTIVE_CURRENT_EXACT` requires this exact
current manual process plus fresh Architecture-133 runtime admission; it
never grants a fresh start. No arbitrary Python process is selected or started.

Runtime observation permits only the current immutable production interpreter,
exact original `-I -S -B` launcher invocation, cwd, fixed paths, module origins,
standard non-impersonating Trading token, full bounded substrate/dependency
inventory, configuration absence, and repeated no-drift observations. The
accepted launcher remains inert/fail-closed. Installation-only preflight does
not invent runtime evidence; full readiness remains unavailable until a
genuinely applicable separately reviewed manual runtime exists.

Pre-install absence can return `INSTALL_REQUIRED`/execute eligibility with no
runtime process. Exact installation plus absent successor root reports the
closed `READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW` readiness field and
never creates the root. The installation engine/latch effect scope and durable
one-shot ordering remain unchanged; execute adds no process or trading effect.

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
