# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**Current P3-R1 worktree:** `F:\AI\worktrees\ai-trading-bot-p3-r1`  
**Current P3-R1 branch:** `feature/p3-r1-recovery-implementation`  
**Retained P3-R1 implementation checkpoint:** `2b82222fbaee857e02519a0ea3627679d309276d`  
**Current P3-R1 status:** correction required under Architectures 95 + 96  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> Project copies are mirrors only. Always prove the live worktree/branch/HEAD
> before acting. Detailed historical evidence remains in architecture,
> validation, and Git history; this file prioritizes current actionable state and
> regression-prevention rules.

---

## 1. Product goal

Build a conservative automated trading platform that progresses through:

**historical research → deterministic simulation → manual paper → unattended
paper → long paper soak → broker-paper → live-readiness certification → tiny
restricted live → mature automated operation → polished GUI.**

AI/strategy remains subordinate to deterministic risk, reviewed authority,
credential isolation, durable evidence, brokerage/reconciliation,
operating-mode controls, and explicit operator safety gates.

---

## 2. Current worktrees and branch routing

```text
P3-R1 implementation:
  F:\AI\worktrees\ai-trading-bot-p3-r1
  feature/p3-r1-recovery-implementation

paper-cycle lineage:
  F:\AI\ai-trading-bot-paper
  feature/reliable-manual-paper-cycle

integration:
  F:\AI\ai-trading-bot-integration
  develop

GUI worktree:
  F:\AI\ai-trading-bot
  feature/gui-foundation

C3 worktree:
  F:\AI\ai-trading-bot-c3
  accepted C3 feature history
```

Do not reuse another active worktree for P3-R1. Existing historical worktrees,
release directories, diagnostics, and pytest evidence are not moved/cleaned as
incidental housekeeping.

---

## 3. Non-compressible AI execution workflow

ChatGPT/Sol owns architecture, debugging strategy, GitHub exact-diff review,
test/certification gates, production-authority review, and next-step planning.
Codex is a bounded implementation agent.

Model routing:

```text
localized/mechanical/docs/frozen contract   -> Luna Extra High
subtle bounded deterministic implementation -> Sol Medium
native Windows/security/authority/locking/
ordering/crash-recovery/architecture         -> Sol High
```

Do not use subagents unless explicitly requested.

Every bounded Codex task with a frozen checkpoint must start by running:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

The outputs must equal the exact worktree, branch, and HEAD in the task. Any
mismatch is a hard stop. Codex must not self-correct with checkout/switch,
reset, rebase, clean, branch recreation, or worktree creation/move/deletion.

These safeguards are never removed for token efficiency. Token-efficient prompts
may omit repeated architecture background, but must retain:

- exact worktree/branch/HEAD startup gate;
- stop-on-mismatch behavior;
- Windows test-isolation requirements;
- exact-file staging rules;
- commit/push authorization state;
- relevant production/provider/credential prohibitions.

Normal implementation flow:

```text
ChatGPT freezes architecture/scope
-> Codex proves startup gate
-> Codex implements only bounded change
-> Codex runs focused isolated tests/checks
-> Codex reports without commit/push unless explicitly authorized
-> user creates/pushes exact checkpoint when instructed
-> ChatGPT reviews exact GitHub diff
-> one broad local certification only after source-diff acceptance
-> release/deployment/operator gates only after source certification
```

Do not use `git add .` or `git add -A` for a scoped checkpoint. Do not merge,
rebase, amend, force-push, change PR metadata, resolve review threads, or modify
unrelated files without explicit approval.

Canonical workflow detail: `docs/AI_DEVELOPMENT_WORKFLOW.md`.

---

## 4. Mandatory Windows pytest isolation

The default user pytest temp hierarchy has repeatedly been inaccessible:

```text
C:\Users\John\AppData\Local\Temp\pytest-of-John
```

Every controlled Windows pytest gate now uses a fresh unique external basetemp
under:

```text
F:\AI\temp\pytest\
```

and normally:

```text
-p no:cacheprovider
```

when cache behavior is irrelevant.

New tests use `tmp_path`/`tmp_path_factory` or another explicitly supplied
scratch root. Do not intentionally use worktree `.pytest_cache` as general native
filesystem scratch. Do not delete, take ownership of, repair, or repurpose
historical pytest/cache directories merely to make a gate pass.

Legacy hard-coded harnesses may use a proven clean-harness fallback only after
exact `PYTHONPATH`/module `__file__` provenance proves the reviewed source is
under test.

---

## 5. Frozen production authority and C3 state

Authority chain:

```text
ValidatedProductionAuthority (C1)
        ↓
WindowsTransactionalAuthority (C2)
        ↓
WindowsEffectfulDailySnapshotCapture (C3)
        ↓
isolated Windows child
        ↓
Windows Credential Manager
        ↓
Alpaca market-data API
```

Frozen runtime facts:

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production TEMP/TMP: F:\AITradingBot\temp
Authority DB: F:\AITradingBot\Authority\authority.sqlite3
Capture output: F:\AITradingBot\Authority\capture-output
Paper final root: F:\AITradingBot\Paper
Paper staging root: F:\AITradingBot\.Paper.provisioning-v1
Production SQL bytes: 118896
Production SQL SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
SQLite: 3.50.4
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

C3 final accepted source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. No provider call #7 is
authorized. Call #5 is permanently `FAILED / CONFIRMED` and non-retryable.
Call #6 is permanently `SUCCEEDED / CONFIRMED` and `SUCCESS_SELECTED`; its
provider effect must never be rerun.

Selected call #6:

```text
request digest: 67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
session: f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt: e809f393-b557-5c6b-8665-78d66822fee8
claim: 487618c1-a5a5-5dd9-971d-a1ea843194c5
reservation: fa5b4538-e475-5a13-9cb2-0d7936232c84
execution: d85a8085-137b-55c2-9679-cddade4a5907
terminal: b4c76e5f-44bb-54ce-a917-3e3223b84107
selection: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact bytes: 1291
artifact identity SHA-256: c23b0c5a8cd5d4808bb18e5f5165344a8013b4c29b9930dc33f74a30846978f2
```

`/v2` credential references are immutable historical state. Any future rotation
requires separately reviewed `/v3` or later authority.

---

## 6. Architecture 94 paper-cycle status

Product flow:

```text
verified selected C3 snapshot
-> offline deterministic strategy history/plan
-> target/planner proposal
-> deterministic risk
-> simulated paper execution
-> verified successor checkpoint/lineage
-> durable Architecture-67 transition/receipt evidence
```

Architecture 94 remains simulated paper. It does not authorize broker/live,
unattended scheduling, automatic retry, GUI execution, online history fill, or
another C3 provider effect.

### P1 — ACCEPTED

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

P1 is pure deterministic strategy-history/plan logic. Its selected-C3 assertion
contains only non-authorizing selection/session/terminal/snapshot IDs and
artifact SHA/length.

### P2 — FULLY ACCEPTED

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

P2 performs the genuine C1-attenuated, read-only selected-C3 proof and issues a
process-local permit. Frozen release wheel:

```text
F:\AI\p2-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
bytes: 743531
SHA-256: 3b4862eb44763bead9cf0dd826645043e7de6419a182664ed780248eae6ff0c0
```

The one supervised P2 reread of already-durable successful call #6 passed after
sealed deployment and a separate non-admin zero-provider preflight. It performed
no provider call, no DB mutation, zero Python socket connects, and no provider
call #7. **Do not rerun the supervised P2 call-#6 read.**

---

## 7. P3 frozen account and production provisioning state

Frozen paper account:

```text
paper account ID: d1510a4b-6ebf-58ef-92a4-e743ca91151e
genesis checkpoint ID: 7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7
starting cash: 100000
genesis SHA-256: b6172753ee4f30a82265ff38b341c3de42869ba6af7ccb69739234135183026d
genesis bytes: 534
anchor SHA-256: 650b977db5ea5f5f1d89e3ed5bf52dfb5b2c5c44c3b34ccceb6d22dd492df871
anchor bytes: 411
manifest SHA-256: 8505eddd07be2f90d1211ee49a9cac4829d0faff9d88d0dc4c609b209a2e8801
```

Accepted bundle/release evidence:

```text
bundle freeze: F:\AI\p3-paper-provisioning-freeze-v2
release wheel: F:\AI\p3-provisioning-release-v4\ai_trading_bot-0.1.0-py3-none-any.whl
release wheel SHA-256: 86834a81dd21887fafd6efc3af1d2525ff9a37a3229dbea6e8cd7cfaba5b8a27
release wheel bytes: 764270
sealed deployment: P3_SEALED_RUNTIME_DEPLOYMENT_V5=ACCEPTED
Trading zero-provider preflight: ACCEPTED
```

The first native Administrator publication attempt is retained failed evidence:

```text
P3_NATIVE_ADMIN_PROVISIONING_V1=FAILED_RETAINED
PUBLICATION_ERROR_STATE=PUBLICATION_OUTCOME_UNCERTAIN
```

Do not rerun that publisher.

Read-only ambiguity resolution and staging forensic established:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
staging exact inventory/security/bytes/native identities: PASS
authority DB unchanged exact: PASS
```

The staging tree is valid frozen recovery evidence. Do not delete, rename,
repair, resume, or regenerate it outside the reviewed recovery path.

---

## 8. P3-R1 native diagnosis and Architecture 95

Disposable diagnostics proved:

```text
root-only absolute FileRenameInfo rename             -> PASS
retained child directory across root rename          -> ERROR_ACCESS_DENIED
retained direct child file across root rename        -> ERROR_ACCESS_DENIED
retained nested file across root rename              -> ERROR_ACCESS_DENIED
publisher topology with retained descendants         -> ERROR_ACCESS_DENIED
all descendants closed before same root rename       -> PASS
adding FILE_SHARE_DELETE to retained root            -> still denied with descendant
retained root GetFinalPathNameByHandleW after PASS   -> exact final path
```

Therefore the production failure was the retained-descendant-handle ordering,
not the frozen account, ACLs, authority DB, or absolute destination path.

Architecture 95 requires:

```text
complete staging proof with descendants retained
-> record all native identities
-> close every descendant successfully
-> retain/revalidate trusted parent + staging root
-> final still absent
-> FIRST_PRODUCTION_MUTATION=P3_R1_ROOT_RENAME
-> one absolute no-replace retained-root rename
-> exact retained-root final-path proof
-> staging absent / final present
-> reopen final descendants read-only
-> exact pre/post native identity equality
-> complete final proof
-> DB before == after
```

The ordinary publisher must use the corrected ordering for future clean-state
publication but must continue to reject existing staging and never invoke P3-R1
recovery implicitly.

---

## 9. Retained implementation checkpoint and Architecture 96 correction

First P3-R1 implementation checkpoint:

```text
2b82222fbaee857e02519a0ea3627679d309276d
fix: add P3 retained staging recovery
```

Focused final gate on that tree passed:

```text
641 passed, 7 skipped
Ruff: PASS
format: PASS
git diff --check: PASS
```

Exact GitHub review accepted:

- descendant close-before-rename ordering;
- exact retained-root final-path proof;
- exact pre/post descendant native-identity continuity;
- conservative crash/ambiguity semantics;
- ordinary-publisher separation;
- fake-Win32 retained-descendant access-denied behavior.

It was **not accepted as final source** because
`P3R1RecoveryDeploymentExpectation` let the caller choose the expected elevated
operator SID and installed RECORD digest/length. Caller-selected SIDs/digests,
paths, manifests, reconstructed objects, or environment values cannot create
production recovery authority.

Architecture 96 resolves this non-circularly:

```text
accepted corrected source
-> exact post-build wheel/RECORD freeze
-> collect exact elevated Administrator SID
-> canonical p3-r1-recovery-authorization/v1 bytes
-> detached domain-separated signature using external production P-256 signer
-> verify against source-pinned production public key
-> freeze signed authorization evidence
-> deploy exactly authorized wheel
-> runtime verifies signed operator/release/incident facts
-> reconcile installed RECORD/package/import provenance
-> issue private process-local recovery permit
-> permit required directly by native recovery mutation boundary
```

A bootstrap signature cannot authorize recovery; recovery uses a dedicated
signed domain and verifier. Raw signed fields are evidence, not a substitute for
the issued permit.

The same correction pass must also move the opt-in native rename regression away
from worktree `.pytest_cache` to pytest-managed/external-basetemp scratch.

Authoritative docs:

```text
docs/architecture/95-p3-r1-retained-staging-recovery.md
docs/architecture/96-p3-r1-signed-recovery-authorization.md
docs/validation/reliable-manual-paper-cycle-p3-r1-recovery.md
docs/validation/reliable-manual-paper-cycle-p3-r1-signed-authorization.md
```

---

## 10. Next milestone

**Next: Codex Sol High bounded P3-R1 Architecture-96 correction.**

Before implementation, fast-forward the local P3-R1 worktree to the current
remote docs head, then use that exact new HEAD in the mandatory startup gate.
Do not reset/rebase/amend the retained `2b82222...` implementation checkpoint.

Correction scope:

- remove caller-authoritative recovery deployment/operator expectation;
- add strict canonical signed recovery-authorization parsing/verification;
- add private process-local recovery permit/provenance boundary;
- require the permit directly at native recovery mutation admission;
- preserve all accepted Architecture-95 rename/identity/crash behavior;
- fix native disposable test scratch to use pytest-managed temp;
- focused tests only using fresh `F:\AI\temp\pytest\... --basetemp` and normally
  `-p no:cacheprovider`;
- no commit/push until ChatGPT exact-diff handoff unless explicitly authorized.

After corrected exact-diff acceptance:

```text
one broad isolated-basetemp source certification
-> exact release wheel freeze
-> wheel/package/RECORD reconciliation
-> exact Administrator SID collection
-> signed P3-R1 authorization freeze
-> sealed-runtime deployment
-> installed RECORD/package reconciliation
-> read-only retained-staging revalidation
-> explicit one-time production recovery approval
-> Administrator P3-R1 recovery
-> close Administrator shell
-> non-admin Trading P3 acceptance
```

P4 remains blocked until P3 recovery and Trading acceptance complete.

---

## 11. Non-authorizations / hard stops

```text
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PUBLISHER_RERUN=FORBIDDEN
STAGING_DELETE_OR_REPAIR=FORBIDDEN
CALLER_ASSERTED_RECOVERY_AUTHORITY=FORBIDDEN
UNSIGNED_RECOVERY_AUTHORIZATION=FORBIDDEN
P3_TRADING_ACCEPTANCE=BLOCKED_PENDING_RECOVERY
P4_PRODUCTION_EXECUTION=BLOCKED
PROVIDER_CALL_7=NOT_AUTHORIZED
CALL6_PROVIDER_EFFECT_REEXECUTION=FORBIDDEN
P2_SUPERVISED_CALL6_REREAD=DO_NOT_RERUN
PRODUCTION_LIVE=NO-GO
```

No production/provider/Credential Manager/broker/Paper transition effect is
authorized by source tests, documentation, release preparation, or signed
artifact construction alone.

---

## 12. GUI track

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
live execution.

---

## 13. Files to read when resuming P3-R1

Read first:

```text
AGENTS.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
docs/AI_DEVELOPMENT_WORKFLOW.md
docs/architecture/94-p3-production-paper-account-provisioning.md
docs/architecture/95-p3-r1-retained-staging-recovery.md
docs/architecture/96-p3-r1-signed-recovery-authorization.md
docs/validation/reliable-manual-paper-cycle-p3-provisioning.md
docs/validation/reliable-manual-paper-cycle-p3-r1-recovery.md
docs/validation/reliable-manual-paper-cycle-p3-r1-signed-authorization.md
```

When changing C1 trust/signature primitives, also read the relevant C1 Windows
authority architecture, especially Architectures 77 and 80, and preserve
bootstrap/recovery domain separation.

---

## 14. Documentation closeout rule

At every accepted milestone, review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

If a milestone reveals a reusable workflow/recovery lesson, also update
`AGENTS.md`, `docs/AI_DEVELOPMENT_WORKFLOW.md`, and the applicable
validation/acceptance record.

Docs-only closeout does not authorize merge, rebase, amend, force-push,
review-thread resolution, PR metadata changes, unrelated changes, production
recovery, provider effects, credential operations, or live trading.
