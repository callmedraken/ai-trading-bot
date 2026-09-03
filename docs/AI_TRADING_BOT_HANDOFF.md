# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**P3-R1 worktree:** `F:\AI\worktrees\ai-trading-bot-p3-r1`  
**P3-R1 branch:** `feature/p3-r1-recovery-implementation`  
**Architecture-100 source-certified checkpoint:** `8cfbbd3a30eb704e6acfc1866bf2ed752879e231`  
**Architecture-100 source-certified tree:** `fc682a5baf35f2f2e8b01c9f8f04ce318681ee85`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> Project copies are mirrors only. Always prove the live worktree, branch, and
> HEAD before acting. Architecture/validation documents and Git history remain
> authoritative for detailed contracts and historical evidence.

---

## 1. Product goal

Build a conservative automated trading platform that progresses through:

**historical research → deterministic simulation → manual paper → unattended
paper → long paper soak → broker-paper → live-readiness certification → tiny
restricted live → mature automated operation → polished GUI.**

AI/strategy is always subordinate to deterministic risk, reviewed authority,
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

Do not reuse another active worktree for P3-R1. Do not clean, reset, rebase,
move, delete, or repair unrelated worktrees or retained evidence.

---

## 3. Mandatory AI/Codex workflow

ChatGPT/Sol owns architecture, debugging strategy, GitHub exact-diff review,
test/certification gates, production-authority review, and next-step planning.
Codex is a bounded implementation agent; ChatGPT may directly handle tiny,
tightly scoped tasks and canonical documentation closeout.

Model routing:

```text
localized/mechanical/frozen-contract work  -> Luna Extra High
subtle bounded implementation              -> Sol Medium
native Windows/security/authority/locking/
ordering/crash-recovery/architecture        -> Sol High
```

Do not use subagents unless explicitly requested.

Every bounded Codex task with a frozen checkpoint begins with:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

The outputs must equal the exact worktree, branch, and HEAD supplied in the task.
Any mismatch is a hard STOP. Codex must not self-correct with checkout/switch,
reset, rebase, clean, branch recreation, or worktree creation/move/deletion.

Implementation flow:

```text
ChatGPT freezes architecture/scope
-> Codex proves startup gate
-> Codex changes only bounded files
-> Codex runs focused isolated tests/checks
-> when explicitly authorized, Codex stages exact files, commits, and ordinary-pushes
-> ChatGPT reviews exact GitHub diff
-> user runs broad/full local certification only after source-diff acceptance
-> release/deployment/operator effects remain separate later gates
```

Never use `git add .` or `git add -A` for a scoped checkpoint. Never merge,
rebase, amend, force-push, change PR metadata, resolve review threads, or modify
unrelated files without explicit approval.

---

## 4. Windows pytest isolation

Every controlled Windows pytest invocation uses a fresh explicit external
basetemp under:

```text
F:\AI\temp\pytest\<fresh-unique-name>
```

and normally:

```text
-p no:cacheprovider
```

when cache behavior is irrelevant.

New tests use pytest-managed temp paths or another explicitly supplied external
scratch root. Never intentionally use worktree `.pytest_cache` as native
filesystem scratch. Preserve inaccessible or malformed historical pytest/cache
evidence rather than deleting or taking ownership merely to make a gate pass.

Legacy authority harnesses may still hard-code `.pytest_cache` scratch. If that
scratch is inaccessible, do not repair/delete it merely for certification. Use a
previously validated clean harness only when the test contract permits it, force
`PYTHONPATH` to the exact reviewed source, print and verify affected module
`__file__` provenance, and rerun only the invalidated legacy slice.

---

## 5. Frozen C3 production state

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

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains permanently
`FAILED / CONFIRMED`; call #6 remains permanently `SUCCEEDED / CONFIRMED` and
`SUCCESS_SELECTED`. Never rerun call #6 and never authorize provider call #7
without a new architecture checkpoint.

Frozen production authority facts include:

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production TEMP/TMP: F:\AITradingBot\temp
Authority DB: F:\AITradingBot\Authority\authority.sqlite3
Capture output: F:\AITradingBot\Authority\capture-output
Paper final root: F:\AITradingBot\Paper
Paper staging root: F:\AITradingBot\.Paper.provisioning-v1
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

---

## 6. Architecture 94 paper-cycle status

### P1 — ACCEPTED

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

### P2 — FULLY ACCEPTED

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

P2's one supervised production reread of the already-durable successful C3 call
#6 passed. **Do not rerun that supervised read.**

Architecture 94 remains simulated paper only: no broker/live trading, unattended
scheduling, automatic retry, or additional C3 provider effect.

---

## 7. P3 retained production-recovery state

The first Administrator paper-root publication attempt failed and remains
retained. Do not rerun it. Read-only resolution established:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
production authority DB: unchanged exact
```

Architectures 95 and 96 remain the retained-staging recovery and signed recovery
authorization contracts. The staging tree remains retained evidence and must not
be deleted, renamed, repaired, regenerated, or implicitly recovered.

---

## 8. Architectures 97–100 — current P3-R1 security line

Current authoritative documents:

```text
docs/architecture/97-p3-r1-recovery-signing-trust-reestablishment.md
docs/architecture/98-p3-r1-ksp-machine-key-security-contract.md
docs/architecture/99-p3-r1-ordinary-nonadmin-test-principal.md
docs/architecture/100-p3-r1-protected-account-ceremony-evidence-root.md

docs/validation/p3-r1-ordinary-nonadmin-test-principal-creation-ceremony.md
docs/validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md
docs/validation/p3-r1-ksp-disposable-test-harness.md
```

Architecture 97 re-establishes the recovery-signing trust path. Architecture 98
freezes the Windows KSP machine-key security experiment. Architecture 99 adds the
separate ordinary non-admin denial perspective using a dedicated new local test
principal. Architecture 100 corrects the account-ceremony retained-evidence
filesystem boundary before any account/root effect occurs.

### Architecture 99 identity

Exact candidate name:

```text
P3R1KspTestUser
```

Its Windows SID is deliberately unknown until a separately authorized create-new
ceremony and Windows readback. The identity may never become production runtime,
Trading, recovery, signing, KSP owner/ACE, or Credential Manager authority.

Accepted Architecture-99 docs checkpoint:

```text
89506d9104b4699d19eee96aac2ad0b18ee25e4a
docs: define P3-R1 ordinary non-admin test principal
```

Creation-ceremony contract:

```text
022960a3f242ded927edf3ae4667f87e724aeb19
docs: define P3-R1 test-user creation ceremony
```

The ceremony uses one-shot direct Netapi32 account creation, exact dual
name-absence proof, secure in-process `SecureString` handling, independent SID
readback/mapping, a deterministic conditional BUILTIN\Users branch, genuine
process-token qualification, sanitized retained evidence, and no automatic
retry/rollback/cleanup/repair.

### Architecture 100 source-certified helper

The original disabled helper checkpoint was:

```text
d509537b88f66ef244d326e5417d38d9e5f25f53
test: add disabled P3-R1 test-user ceremony helper
```

Architecture 100 then retired the unsafe retained root under `F:\AI` and froze:

```text
RETIRED:
F:\AI\p3-r1-ordinary-nonadmin-principal-v1

NEW:
F:\p3-r1-ordinary-nonadmin-principal-v2

SCHEMA:
p3-r1-ordinary-nonadmin-principal-evidence/v2
```

The accepted implementation checkpoint is:

```text
8cfbbd3a30eb704e6acfc1866bf2ed752879e231
test: implement protected P3-R1 ceremony evidence root

tree:
fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
```

Changed only:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

The source implements the create-time protected DACL, exact creator/SYSTEM/
Administrators security semantics, parent replacement-authority gates, fixed NTFS
volume/root identity binding, reparse-safe/no-delete-share continuity, strict v2
root-identity evidence, and fail-closed collision/uncertain-create handling. The
separate KSP evidence root remains unchanged:

```text
F:\AI\p3-r1-ksp-disposable-test-v1
```

The helper remains source-only and disabled:

```text
ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false
```

No password prompt, evidence-root creation, ACL/account/group mutation, KSP,
production recovery, signing, or provider effect occurred.

### Architecture 100 certification

Certification is accepted:

```text
focused helper gate: 47 passed
broad repository run: 3862 passed before legacy harness environment failures
legacy harness recovery: 758 passed
Ruff check: passed
Ruff format check: passed
git diff --check: passed
reviewed HEAD/tree unchanged exact
P3-R1 worktree clean
```

The broad-run failures were not accepted as source defects. They all traced to
unchanged legacy authority harnesses attempting to use the inaccessible hard-coded
P3-R1 path:

```text
F:\AI\worktrees\ai-trading-bot-p3-r1\.pytest_cache\ai-trading-bot-lifecycle-arbiters-v1
```

Both affected test files were byte-identical to `develop`. They were rerun from
the validated integration harness with `PYTHONPATH=F:\AI\worktrees\ai-trading-bot-p3-r1\src`; printed `__file__` provenance proved the imported `trading_bot`
modules came from the reviewed P3-R1 source, and the entire two-file legacy slice
passed 758/758. Do not rerun the full repository suite unless source changes.

---

## 9. Immediate next milestone — restart read-only readiness from gate #1

Architecture 100 is **SOURCE CERTIFIED**. Do not resume the old stopped readiness
run at its former DACL checkpoint. Start a new complete readiness sequence from
gate #1.

The restart is read-only and must freshly prove/freeze:

1. exact P3-R1 worktree, branch, source commit/tree, helper/wrapper/test hashes,
   and the exact future source-enablement diff;
2. absence of both the retired v1 account evidence root and the new v2 root;
3. current `F:\` fixed/local NTFS volume GUID/serial and persistent-ACL support;
4. `F:\` no-reparse identity and current owner/DACL semantics, including no
   untrusted `FILE_DELETE_CHILD`, `WRITE_DAC`, or `WRITE_OWNER` authority capable
   of replacing the future protected child;
5. exact creator and Trading identities plus built-in SID mappings;
6. candidate-name absence and relevant direct/indirect/token/special-group
   topology;
7. password/account/logon policy prerequisites;
8. exact Windows PowerShell 5.1, helper, Git, and `netapi32.dll` identities; and
9. confirmation that all filesystem/account/group/KSP/provider/production effects
   remain disabled.

Any changed, missing, ambiguous, pre-created, reparse, volume-mismatched, or
unexpectedly writable observation is a STOP. Do not repair ancestors, retained
cache, production staging, or a candidate root to make readiness pass.

The later root/account authorization, if readiness eventually succeeds, must be
one-shot across process loss. Once an authorized root-creation call may have
begun, an ambiguous process termination consumes that authorization and permits
only read-only reconciliation—not another launch simply because the fixed root
appears absent.

---

## 10. Effect authorization — still blocked

The following remain **NOT AUTHORIZED**:

- creation of the new v2 evidence root;
- ACL/security-descriptor mutation on Windows;
- password prompting, capture, or serialization;
- `P3R1KspTestUser` creation/reset/delete/rename/enable/disable;
- local-group mutation;
- source SID freeze in the KSP harness;
- native KSP experiment execution or cleanup;
- production P3 retained-staging recovery;
- provider call #7;
- brokerage or live trading; and
- unrelated production/provider/credential effects.

Expected chain from the current source-certified checkpoint:

```text
complete read-only Architecture-100 readiness restart from gate #1
-> ChatGPT acceptance of frozen readiness evidence
-> separate explicit one-time filesystem/account effect authorization
-> protected evidence-root/account ceremony
-> genuine ordinary-user token/group qualification
-> later source SID freeze in the KSP harness
-> separately authorized KSP denial experiment
-> recovery execution only after all independent recovery gates are accepted
```

---

## 11. GUI status

GUI-A1 through GUI-A7 are fully accepted and integrated. GUI capabilities remain
read-only presentation/inspection boundaries. The GUI does not own production
authority, credentials, paper-account mutation, retry, recovery, brokerage, or
execution.

---

## 12. Stable project constraints

- US stocks and ETFs;
- long-only;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability.

---

## 13. Closeout rule

At every accepted checkpoint review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only when a new reusable workflow lesson
is discovered that is not already covered.

Git-tracked documents are authoritative. Documentation closeout does not itself
authorize merge, rebase, force-push, amend, review-thread resolution, PR metadata
changes, production/provider effects, Windows security effects, or unrelated
modifications.
