# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`
**Integration branch:** `develop`
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`
**Current Architecture-94 worktree:** `F:\AI\ai-trading-bot-paper`
**Current Architecture-94 branch:** `feature/reliable-manual-paper-cycle`
**Accepted P2 source head:** `a810122a96b6fc90da25d71eede8da64b7272c98`
**C3 production release-source checkpoint:** `82ba29ae2c2cc6bb3544077db0ee21868e6d5693`
**Handoff status:** August 30, 2026 — C3 is FULLY COMPLETE / ACCEPTED; Architecture-94 P1 is ACCEPTED; Architecture-94 P2 read-only selected-C3 authority is FULLY ACCEPTED through source review, local regression, frozen release artifact, sealed production deployment, non-admin Trading zero-provider preflight, and one supervised read-only reread of the already-consumed successful call #6; P3 fixed-root paper-account authority is NEXT and should be implemented with Codex Sol High; all six C3 provider effects remain consumed; no provider call #7 is authorized; `/v2` credential references remain immutable historical state; GUI through A7 remains accepted; production/live trading remains NO-GO.

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> Project copies are mirrors only. Always verify the live branch/head before
> acting. Historical details remain in the architecture/validation documents and
> Git history; this handoff intentionally prioritizes current actionable state
> and regression-prevention rules.

---

## 1. Product goal

Build a conservative automated trading platform that progresses through:

**historical research → deterministic simulation → manual paper → unattended
paper → long paper soak → broker-paper → live-readiness certification → tiny
restricted live → mature automated operation → polished GUI.**

AI/strategy remains subordinate to deterministic risk, reviewed authority,
credential isolation, brokerage/reconciliation, operating-mode controls, durable
evidence, and operator emergency controls.

**Production/live trading remains NO-GO.**

---

## 2. Worktrees and branch routing

Current worktree map:

```text
paper-cycle feature:
  F:\AI\ai-trading-bot-paper
  feature/reliable-manual-paper-cycle
  upstream origin/feature/reliable-manual-paper-cycle

integration:
  F:\AI\ai-trading-bot-integration
  develop

GUI historical/active worktree:
  F:\AI\ai-trading-bot
  feature/gui-foundation

C3 worktree:
  F:\AI\ai-trading-bot-c3
  accepted C3 feature branch/history
```

Do not use `F:\AI\ai-trading-bot` for Architecture-94 paper-cycle implementation.
Before any Codex task, local certification, packaging, or release work, prove the
absolute worktree, branch, expected HEAD, expected upstream, and clean tracked
status. Stop on mismatch.

Preserve unrelated generated/untracked reports and historical pytest directories.
Do not prune old worktrees, clean permission-warning pytest trees, or delete
release/quarantine directories as an incidental step.

---

## 3. AI development workflow

Use ChatGPT/Sol for architecture, debugging strategy, GitHub/diff review,
test-gate/certification decisions, production-authority review, release gating,
and the next-step plan.

Model routing:

```text
localized/mechanical/docs/frozen contract  -> Luna Extra High
subtle bounded deterministic implementation -> Sol Medium
native Windows/security/authority/locking/
ordering/crash-recovery/architecture        -> Sol High
```

Do not use subagents unless explicitly requested.

Normal implementation flow:

```text
ChatGPT freezes scope/contract
-> Codex implements in exact worktree
-> Codex runs focused tests/checks
-> exact reviewable Git checkpoint is pushed when instructed
-> ChatGPT reviews exact GitHub commit/diff
-> user runs broader/final local gate only on reviewed unchanged source
-> ChatGPT accepts/rejects and supplies next milestone
```

Do not use `git add .`. Do not merge, rebase, amend, force-push, change PR
metadata, resolve review threads, or modify unrelated files without explicit
approval.

The expanded reusable workflow, including Windows pytest recovery and production
runtime deployment, is canonical in `docs/AI_DEVELOPMENT_WORKFLOW.md`.

---

## 4. Current production authority architecture

```text
ValidatedProductionAuthority (C1)
        ↓
WindowsTransactionalAuthority (C2)
        ↓
WindowsEffectfulDailySnapshotCapture (C3)
        ↓
isolated suspended Windows child
        ↓
Windows Credential Manager
        ↓
Alpaca market-data API
```

C2 is effectfully inert without the reviewed C3 bridge. C3 authorizes only the
reviewed market-data capture path and never brokerage, paper mutation, or live
trading.

Core native effect ordering remains:

```text
CreateProcessW suspended
-> durable C2 execution / PRE_RESUME_READY
-> write canonical child request
-> close request writer
-> commit ResumeIntent
-> ResumeThread exact primary thread once
-> bounded child/process observation
-> cleanup evidence
-> independent parent verification
-> terminal / publication / selection
```

`RESUME_RECORDED` is lifecycle evidence, not provider-success evidence.
Ambiguous external effects fail closed.

---

## 5. Frozen production facts

```text
Trading account:
  DESKTOP-I4DOKM7\Trading
Trading SID:
  S-1-5-21-1397534616-3988210162-180023805-1009
Fixed runtime:
  F:\AITradingBot\runtime\python.exe
Runtime directory:
  F:\AITradingBot\runtime
Production TEMP/TMP:
  F:\AITradingBot\temp
Authority DB:
  F:\AITradingBot\Authority\authority.sqlite3
Capture output:
  F:\AITradingBot\Authority\capture-output
Architecture-94 paper root:
  F:\AITradingBot\Paper
Credential policy:
  windows-credential-manager-alpaca-market-data/v2
Credential targets:
  AITradingBot/MarketData/Alpaca/ApiKeyId/v2
  AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
Frozen production SQL bytes:
  118896
Frozen production SQL SHA-256:
  aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
SQLite build observed during P2 deployment:
  3.50.4
```

`/v2` is immutable historical credential-reference state. Do not regenerate,
delete, replace, restage, or rotate those targets in place. A later rotation
requires separately reviewed `/v3` or later authority.

---

## 6. C3 status — FULLY COMPLETE / ACCEPTED

C3 final source head:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six actual C3 real-provider effects are consumed. No provider call #7 is
authorized.

Call #5 is permanently historical:

```text
terminal: FAILED / CONFIRMED
child/provider path: provider succeeded
parent result: artifact publication failed
selection: none
retry: NEVER
```

Final successful call #6:

```text
ordered universe: SPY
request window: 2026-08-28 through 2026-08-28
authorized XNYS snapshot session: 2026-08-28
request digest:
  67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
session_id:
  f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt_id:
  e809f393-b557-5c6b-8665-78d66822fee8
claim_id:
  487618c1-a5a5-5dd9-971d-a1ea843194c5
reservation_id:
  fa5b4538-e475-5a13-9cb2-0d7936232c84
execution_id:
  d85a8085-137b-55c2-9679-cddade4a5907
terminal_id:
  b4c76e5f-44bb-54ce-a917-3e3223b84107
selection_id:
  36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id:
  eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256:
  31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length:
  1291
terminal:
  SUCCEEDED / CONFIRMED
session/attempt:
  SUCCESS_SELECTED
```

Call #6 is successful **and consumed**. Its durable evidence/artifact may be
reread by a reviewed read-only boundary; its provider effect may never be rerun.

---

## 7. Architecture 94 contract

Architecture 94 composes the accepted deterministic paper stack without turning
C3 selection into execution authority:

```text
selected verified C3 snapshot
+ explicit offline strategy-history seed
+ authoritative paper-account tip
        ↓
pure deterministic strategy plan
        ↓
existing target/planner/proposal path
        ↓
existing deterministic portfolio risk
        ↓
existing simulated paper execution
        ↓
verified successor checkpoint + full lineage
        ↓
Architecture-67 durable transition + receipt
```

Non-negotiable rules:

- durable state outranks process assumptions;
- UUIDs, paths, filenames, digests, timestamps, reconstructed objects, and caller
  assertions cannot create authority;
- strategy/GUI/AI cannot bypass deterministic risk;
- C3 capture authority cannot become paper mutation authority;
- no provider call #7, online history fill, broker call, scheduler, automatic
  retry, or GUI execution control is introduced by Architecture 94;
- Architecture 67 remains the only paper transition commit/recovery algorithm.

Detailed frozen contract:
`docs/architecture/94-reliable-manual-paper-cycle-authority.md`.

---

## 8. P1 — ACCEPTED

Accepted P1 head:

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

P1 implements the pure strategy-history seed and deterministic
`ManualPaperStrategyPlan` boundary.

Important accepted P1 boundary:

`ManualPaperSelectedC3Assertion` carries only:

- selection ID;
- session ID;
- terminal ID;
- snapshot ID;
- artifact SHA-256;
- artifact byte length.

Those are pure non-authorizing assertions. P1 does **not** bind
`artifact_identity_sha256`, `C3ArtifactIdentityEvidence`, native file identity,
filesystem facts, or a P2 permit. P2 independently proves those facts; P4 later
exact-compares P1 assertions to P2 audit evidence.

P1 local gate:

```text
198 passed
Ruff: PASS
format: PASS
diff checks: PASS
exact tree: clean
```

---

## 9. P2 — FULLY ACCEPTED

Accepted P2 source head:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

P2 provides a sealed production reader only from genuine
`ValidatedProductionAuthority`. It opens the fixed authority DB read-only via
the approved VFS, reads one exact selected lineage in one consistent query-only
transaction, proves the exact terminal/selection semantics, safely reopens only
the canonical artifact derived from durable snapshot ID, reconstructs C3
artifact-identity evidence, strictly verifies the snapshot, then issues a
process-local permit bound to the exact successful read/audit/reader/core
provenance.

Accepted source review:

```text
P2_B1_RETAINED_BYTES_BINDING=PASS
P2_B2_PERMIT_PROVENANCE=PASS
P2_B2_C1_ATTENUATION=PASS
P2_B3_DURABLE_SEMANTICS=PASS
P2_READ_ONLY_SQLITE_BOUNDARY=PASS
P2_ARTIFACT_IDENTITY_PROOF=PASS
P2_C1_C2_REGRESSION_REVIEW=PASS
P1_BOUNDARY_PRESERVED=PASS
P2_SOURCE_REVIEW=PASS
```

Local acceptance:

```text
P2 focused file: 48 passed
selected C2 regression cases: 77 passed
Ruff / format / diff checks: PASS
tracked paper worktree: clean
```

### P2 Windows pytest lesson

Do not repeat the earlier environment detour.

The user-temp path
`C:\Users\John\AppData\Local\Temp\pytest-of-John` can be inaccessible. Controlled
Windows gates should use a fresh explicit `--basetemp F:\AI\pytest-*` path.

The paper worktree also has historical/malformed `.pytest_cache` state that can
block the C2 test-only lifecycle arbiter, whose scratch path is intentionally
worktree-local and therefore unaffected by `--basetemp`. Do not delete, take
ownership of, chmod, or casually move that cache to make a test pass. For P2,
the accepted solution was to run the unchanged C2 harness from the validated
integration worktree while forcing `PYTHONPATH=F:\AI\ai-trading-bot-paper\src`
and printing affected module `__file__` paths first. All affected imports proved
they came from the exact reviewed P2 paper source, and 77 cases passed.

### P2 release artifact

P2 was built from a detached Git export after source acceptance:

```text
source commit:
  a810122a96b6fc90da25d71eede8da64b7272c98
source tree:
  51936b0af02b2a0246dc67b2e30d11a5c5e09b31
source export:
  F:\AI\p2-production-source-v1
wheel:
  F:\AI\p2-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
wheel bytes:
  743531
wheel SHA-256:
  3b4862eb44763bead9cf0dd826645043e7de6419a182664ed780248eae6ff0c0
wheel entries:
  215
package source files:
  211 exact matches
RECORD rows / hashed payloads:
  215 / 214
```

### P2 deployment and trust-context lesson

The first fixed-runtime provenance probe correctly showed the runtime was stale
for P2. The correct response was **not** to copy source into `site-packages`.
The accepted path was detached export → frozen wheel → exact verification →
elevated sealed replacement → installed RECORD/source reconciliation → frozen
SQL proof → ownership/ACL normalization → exact Trading RX publication →
non-admin Trading zero-provider preflight.

Use three distinct trust contexts:

```text
normal development account -> Git/source/test/artifact work
elevated Administrator     -> fixed-runtime install/ACL publication
non-admin Trading           -> genuine C1/P2 production acceptance
```

An access-denied result against the protected fixed runtime from the normal
account can be the intended ACL boundary, not a missing runtime.

Installed P2-sensitive source hashes:

```text
runtime/__init__.py
  6630a2edca0b09f850eab269f1cfe35c845a2baebac75315387b0470977295c1
runtime/manual_paper_selected_c3_snapshot.py
  ef49baff52712f3c5c34d760719b0fde2a5ccaf83ba0ceaccdaca15a9c694e8a
runtime/windows_authority_schema.py
  0784ebce1231a018e5c68f78cedf578c04d066ec549a603e098163ad0233d56f
runtime/windows_authority_validation.py
  1f7355e6603af9bf53a81761fd244e895c2d47c3309933abde887a1b616c0299
runtime/windows_transactional_authority.py
  6a847e4385f4ad516031c0c93c572ef98c45a514de41e680e4e8c3828e354874
```

Ownership normalization processed 12,502 files with zero failures; the sealed
post-install runtime contained 12,501 descendants and zero ACL anomalies before
Trading RX publication.

### P2 non-admin zero-provider preflight

Under exact non-admin `DESKTOP-I4DOKM7\Trading`:

```text
C1_AUTHORITY_ACQUIRED=PASSED
P2_READER_CONSTRUCTED=PASSED
P2_PUBLIC_AUTHORITY_ATTRIBUTE_PRESENT=False
P2_SELECTED_SNAPSHOT_READ_PERFORMED=False
P2_PERMIT_ISSUED=False
SOCKET_CONNECT_COUNT=0
RUNTIME_WRITE_BLOCKED=True
TEMP_WRITE_READ_DELETE=PASSED
NETWORK_OPERATION_PERFORMED=False
PRODUCTION_CHILD_LAUNCHED=False
PROVIDER_REQUEST_PERFORMED=False
AUTHORITY_DATABASE_MUTATION=False
```

Windows PowerShell 5.1 rejected the earlier operator command
`New-Item -LiteralPath`. The corrected write-denial/temp probe used
`[System.IO.File]`. Treat shell incompatibility as an operator-command defect,
not a product regression.

### Final supervised P2 reread of accepted call #6

The one accepted P2 reread occurred only after the zero-provider preflight. It
reread existing durable state/artifact and did **not** execute the C3 provider
effect again.

Accepted P2 audit:

```text
selection:
  36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
session:
  f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt:
  e809f393-b557-5c6b-8665-78d66822fee8
terminal:
  b4c76e5f-44bb-54ce-a917-3e3223b84107
snapshot:
  eba46838-44ae-5bec-97bf-98c6639ae6a7
terminal state:
  SUCCEEDED
provider disposition:
  CONFIRMED
artifact SHA-256:
  31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length:
  1291
artifact identity SHA-256:
  c23b0c5a8cd5d4808bb18e5f5165344a8013b4c29b9930dc33f74a30846978f2
canonical artifact:
  F:\AITradingBot\Authority\capture-output\daily-market-data-snapshot-eba46838-44ae-5bec-97bf-98c6639ae6a7.json
```

Verifier/permit result:

```text
retained bytes SHA/length: exact
SNAPSHOT_VERIFICATION_PASSED=True
SNAPSHOT_DIAGNOSTICS=()
RESULT_PROVIDER_CALL_PERFORMED=False
RESULT_DATABASE_MUTATION_PERFORMED=False
P2_PRODUCTION_PERMIT_VALID=True
SOCKET_CONNECT_COUNT=0
```

Authority database before/after:

```text
331776 bytes
SHA-256:
  6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76
AUTHORITY_DATABASE_BYTE_IDENTITY=PASSED
```

Selected artifact before/after:

```text
1291 bytes
SHA-256:
  31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
CALL6_ARTIFACT_BYTE_IDENTITY=PASSED
```

Final classification:

```text
P2_SUPERVISED_CALL6_READ=PASSED
CALL6_PROVIDER_EFFECT_REEXECUTED=False
PROVIDER_CALL_7_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
P2=FULLY_ACCEPTED
```

Detailed acceptance record:
`docs/validation/reliable-manual-paper-cycle-p2-acceptance.md`.

---

## 10. Next milestone — P3 manual paper-account authority

P3 is next. Route implementation to **Codex Sol High** because it crosses
security/authority, filesystem trust, locking/concurrency, and crash/recovery
boundaries.

Frozen P3 scope:

- production-style root fixed in code at `F:\AITradingBot\Paper`;
- no caller-selected operational root;
- explicit disposable test seams only;
- immutable account anchor binding canonical paper account ID, approved machine
  authority identity, exact Trading SID, and exact genesis checkpoint
  ID/SHA-256/byte length;
- safe root/object/reparse/DACL/owner/inheritance validation;
- bounded strict inventory of recognized durable state;
- current tip derived only from a unique verified linear graph from anchored
  genesis;
- forks, cycles, competing successors, disconnected genesis, staging remnants,
  malformed recognized state, unsafe objects, casefold collisions, overflow, or
  unverifiable transitions block admission;
- one account-scoped Windows lifecycle mutex;
- complete anchor/graph/tip revalidation after mutex acquisition;
- mutex held through complete Architecture-67 execute/recover durable
  classification;
- mutex never substitutes for durable transition/receipt evidence;
- no C3/provider/credential/broker/live authority.

After P3: P4 exact P1↔P2↔paper-account composition, P5 explicit manual CLI,
then P6 supervised simulated-paper acceptance/final certification.

---

## 11. GUI track

GUI-A1 through GUI-A7 are fully accepted and integrated. Accepted semantic GUI
head:

```text
7fb2e0b014938215e9ab4fbdb1cddde2651fad92
```

Final GUI documentation/reference-correction head:

```text
5c1944d19416d0fdd6c4ff681e2ebda01d83ead4
```

The GUI remains presentation/read-only inspection. It does not own production
authority, capture, credentials, paper mutation, retry/recovery, brokerage, or
live execution. No GUI-A8 architecture is currently selected.

---

## 12. Stable product constraints

- US stocks/ETFs initially;
- long-only;
- no margin/leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability;
- production/live remains NO-GO until separately certified.

---

## 13. Files to read when resuming

Read these first:

```text
AGENTS.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
docs/AI_DEVELOPMENT_WORKFLOW.md
docs/architecture/94-reliable-manual-paper-cycle-authority.md
docs/validation/reliable-manual-paper-cycle-plan.md
docs/validation/reliable-manual-paper-cycle-p2-acceptance.md
```

When working near C1/C2/C3, also read the relevant Windows authority/C3
architecture documents, especially Architectures 77, 80, 81, 82, 83, 84, and
84A.

When working on P3/P4, also read the accepted deterministic paper-account,
checkpoint, lineage, and durable operation architecture (18, 19, 23, 62, 63,
66, and 67) before changing authority or commit semantics.

---

## 14. Documentation and closeout rule

At every accepted milestone, review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

If a milestone teaches a reusable workflow/recovery lesson, also update
`docs/AI_DEVELOPMENT_WORKFLOW.md` and the applicable validation/acceptance record.
This requirement exists specifically to prevent future chats from repeating
already-diagnosed worktree, pytest, shell-compatibility, or production-deployment
mistakes.

Docs-only closeout does not authorize merging, rebasing, amending, force-pushing,
review-thread resolution, PR metadata changes, unrelated file changes, provider
effects, credential operations, or live trading.

---

## 15. Definition of project success

The project succeeds when it can research deterministically, acquire trusted
market data safely, make portfolio decisions under deterministic risk, interact
safely with a brokerage, reconcile ambiguous outcomes, run unattended for long
periods, fail closed on uncertainty, expose durable evidence/operator controls,
operate under strict live limits, and present the same reviewed capabilities
through a polished GUI.

The final system is a **safety-oriented automated trading platform in which AI
is one replaceable decision-making component inside a deterministic operational
and authority framework**.
