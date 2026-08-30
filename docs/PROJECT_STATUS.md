# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot.
The canonical cross-chat handoff is `docs/AI_TRADING_BOT_HANDOFF.md`; detailed
architecture/validation documents remain authoritative for subsystem contracts
and historical decisions.

## Long-term objective

Build a conservative automated trading platform that progresses safely through
historical research, deterministic simulation, manual paper, unattended paper,
long paper soak, broker-paper, live-readiness certification, tiny restricted
live operation, mature automated operation, and a polished end-user GUI.

**Production/live trading: NO-GO.** Live trading remains unavailable until
separately reviewed brokerage, reconciliation, credential, operating-mode,
operator-control, long-soak, and live-readiness gates are complete.

## Current repository and worktree state

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
docs: repair integrated GUI status
```

Architecture-94 paper-cycle work:

```text
worktree: F:\AI\ai-trading-bot-paper
branch: feature/reliable-manual-paper-cycle
upstream: origin/feature/reliable-manual-paper-cycle
accepted P2 source head: a810122a96b6fc90da25d71eede8da64b7272c98
```

The main `F:\AI\ai-trading-bot` worktree remains the GUI worktree and must not
be reused for Architecture-94 paper-cycle implementation. The integration
worktree remains `F:\AI\ai-trading-bot-integration`.

## C3 status — FULLY COMPLETE / ACCEPTED

C1 `ValidatedProductionAuthority` and C2 `WindowsTransactionalAuthority` are the
reviewed authority foundations. C3 is the reviewed bridge into real market-data
credentials, isolated native Windows child execution, Alpaca transport, parent
verification, final-artifact publication, terminal evidence, and durable
selection.

C3 is fully accepted at production release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains
`FAILED / CONFIRMED` and permanently non-retryable. Final call #6 remains
`SUCCEEDED / CONFIRMED` and `SUCCESS_SELECTED`. Its provider effect must never be
rerun. No provider call #7 is authorized. `/v2` Alpaca credential references are
immutable historical state; later rotation requires a separately reviewed `/v3`
or later version.

Accepted call-#6 durable selection:

```text
request digest: 67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
session: f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt: e809f393-b557-5c6b-8665-78d66822fee8
terminal: b4c76e5f-44bb-54ce-a917-3e3223b84107
selection: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
terminal: SUCCEEDED / CONFIRMED
```

## Architecture 94 reliable manual paper cycle

Product flow:

```text
verified selected C3 snapshot
-> explicit offline strategy history
-> deterministic strategy plan
-> target/planner proposal
-> deterministic risk
-> simulated paper execution
-> verified successor checkpoint/full lineage
-> durable Architecture-67 transition/receipt evidence
```

Architecture 94 remains a simulated paper milestone. It does not authorize a
broker, live trading, unattended scheduling, automatic retry, or another C3
provider effect.

### P1 — pure strategy history and deterministic strategy plan: ACCEPTED

Accepted P1 head:

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

P1 preserves its pure boundary. `ManualPaperSelectedC3Assertion` binds only the
selected C3 selection/session/terminal/snapshot IDs plus artifact SHA-256 and
byte length as non-authorizing assertions. P1 does not bind native filesystem
identity, `artifact_identity_sha256`, `C3ArtifactIdentityEvidence`, P2 permits,
or P2 authority.

Accepted P1 local gate: 198 passed, Ruff/format/diff checks passed, exact tree
clean.

### P2 — read-only selected-C3 snapshot authority: FULLY ACCEPTED

Accepted P2 source head:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

P2 source review accepted retained-byte binding, one-shot successful-read permit
provenance, C1 attenuation, complete durable C2/C3 semantic validation,
read-only SQLite, artifact identity reconstruction, and preservation of the P1
boundary.

Local acceptance:

```text
P2 focused tests: 48 passed
selected C2 regression cases: 77 passed
Ruff/format/diff checks: PASS
reviewed worktree: clean at exact P2 HEAD
```

The C2 regression run used the validated integration test harness only after
`PYTHONPATH` and printed module `__file__` values proved that the exact reviewed
paper-worktree P2 source was imported. This was required because the paper
worktree contained an inaccessible historical `.pytest_cache` lifecycle-arbiter
path; that environment was preserved rather than repaired destructively.

Frozen P2 release artifact:

```text
source tree: 51936b0af02b2a0246dc67b2e30d11a5c5e09b31
source export: F:\AI\p2-production-source-v1
wheel: F:\AI\p2-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
wheel bytes: 743531
wheel SHA-256: 3b4862eb44763bead9cf0dd826645043e7de6419a182664ed780248eae6ff0c0
wheel entries / RECORD rows / hashed payloads: 215 / 215 / 214
package source files: 211 exact matches
```

The fixed production runtime was correctly discovered to be stale before P2
acceptance. P2 was therefore deployed through the sealed wheel procedure rather
than by ad-hoc source copying. Installed RECORD reconciliation passed with 214
hashed payloads and zero failures; installed security-sensitive source matched
the frozen export; SQLite remained 3.50.4; frozen production SQL remained exact;
ownership/ACL normalization passed; exact Trading Read & Execute was republished;
and the separate non-admin Trading zero-provider preflight passed.

Final supervised P2 read of the already-consumed successful call #6 passed:

```text
artifact identity SHA-256:
  c23b0c5a8cd5d4808bb18e5f5165344a8013b4c29b9930dc33f74a30846978f2
snapshot verification: PASS
diagnostics: ()
production permit validation: PASS
provider call performed: False
database mutation performed: False
Python socket connects: 0
call #6 provider effect reexecuted: False
provider call #7 performed: False
```

Before/after authority database evidence was byte-identical:

```text
F:\AITradingBot\Authority\authority.sqlite3
331776 bytes
SHA-256: 6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76
```

Before/after selected artifact evidence was also byte-identical at 1291 bytes
and SHA-256 `31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d`.

Detailed P2 evidence is recorded in
`docs/validation/reliable-manual-paper-cycle-p2-acceptance.md`.

### P3 — manual paper-account authority: NEXT

P3 must implement only the frozen Architecture-94 operational paper-account
boundary:

- fixed production-style root `F:\AITradingBot\Paper`;
- immutable account anchor binding canonical account/genesis/machine/principal
  evidence;
- bounded inventory and graph-derived unique verified current tip;
- rejection of forks, cycles, disconnected genesis, staging ambiguity, unsafe
  objects, casefold collisions, and overflow;
- one account-scoped Windows lifecycle mutex;
- complete account revalidation after mutex acquisition;
- mutex held through the existing Architecture-67 execute/recover durable
  classification boundary;
- no provider, broker, credential, C3 mutation, or live authority.

P3 crosses authority, filesystem trust, locking/concurrency, and crash/recovery
semantics, so implementation is routed to **Codex Sol High**, not Luna.

Later stages remain P4 authority/composition join, P5 explicit manual CLI, and
P6 supervised simulated-paper acceptance/final certification.

## Frozen authority/runtime facts

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production temp: F:\AITradingBot\temp
Authority database: F:\AITradingBot\Authority\authority.sqlite3
Capture output: F:\AITradingBot\Authority\capture-output
Paper root reserved by Architecture 94: F:\AITradingBot\Paper
Production SQL bytes: 118896
Production SQL SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

## GUI status

GUI-A1 through GUI-A7 are fully accepted and integrated. The accepted semantic
GUI head is `7fb2e0b014938215e9ab4fbdb1cddde2651fad92`; final GUI
documentation/reference correction head is
`5c1944d19416d0fdd6c4ff681e2ebda01d83ead4`.

GUI capabilities remain read-only presentation/inspection boundaries. GUI does
not own production authority, credentials, paper-account mutation, retry,
recovery, brokerage, or execution. No GUI-A8 architecture is selected.

## Workflow invariants learned during P2

The reusable workflow rules are now canonical in `docs/AI_DEVELOPMENT_WORKFLOW.md`:

- exact worktree/branch/HEAD/upstream/clean guards before implementation or
  certification;
- explicit external `F:\AI\pytest-*` basetemp on Windows when user-temp pytest
  scratch is inaccessible;
- preserve malformed/inaccessible historical pytest caches rather than
  deleting/taking ownership merely to make tests run;
- when a test harness hard-codes worktree-local scratch, use a known-good
  harness only after proving exact reviewed-source import provenance;
- Windows PowerShell 5.1 compatibility must be respected (`New-Item
  -LiteralPath` is not supported there);
- filesystem gate commands must fail terminatingly before any success message is
  printed;
- development, elevated deployment, and non-admin Trading acceptance are three
  distinct trust contexts;
- never assume newly accepted source is already in the fixed runtime; prove
  installed import/source provenance first;
- stale fixed runtime means detached export + frozen wheel + exact offline
  verification + sealed replacement, never ad-hoc source copying.

## Stable product constraints

- US stocks and ETFs;
- long-only;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability.

## Documentation workflow

At every accepted development checkpoint, review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

When a checkpoint reveals a reusable workflow lesson, update
`docs/AI_DEVELOPMENT_WORKFLOW.md` as part of closeout. The Git-tracked documents
are authoritative; uploaded Project copies are context mirrors only.

Documentation closeout does not authorize merge, rebase, force-push, amend,
review-thread resolution, PR metadata changes, production/provider effects, or
unrelated modifications.
