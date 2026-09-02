# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**P3-R1 worktree:** `F:\AI\worktrees\ai-trading-bot-p3-r1`  
**P3-R1 branch:** `feature/p3-r1-recovery-implementation`  
**Architecture-100 checkpoint:** `e2861fab3af7d297d79274db2a82fd134672fb58`  
**Architecture-100 tree:** `d6f9203184d90a0c409d929c25bb2c7e7e520f29`  
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
Codex is a bounded implementation agent.

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
-> Codex reports without commit/push unless explicitly authorized
-> user stages exact paths, commits, and pushes when instructed
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

### Disabled helper checkpoint

```text
d509537b88f66ef244d326e5417d38d9e5f25f53
test: add disabled P3-R1 test-user ceremony helper
```

Changed only:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

The helper remains source-only and disabled:

```text
ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false
```

Ordinary invocation cannot prompt for the account password or dispatch account/
group effects.

### Architecture 100 — accepted docs-only design

Checkpoint:

```text
e2861fab3af7d297d79274db2a82fd134672fb58
docs: define protected P3-R1 ceremony evidence root
```

A stopped read-only ACL/namespace diagnostic proved the old root under `F:\AI`
was incompatible with the strict cross-run retained-path integrity model because
untrusted authority on the ancestor could displace the pathname after in-run
no-delete-share guards were released.

Architecture 100 retires the old root before any effect occurred:

```text
RETIRED:
F:\AI\p3-r1-ordinary-nonadmin-principal-v1

NEW:
F:\p3-r1-ordinary-nonadmin-principal-v2

SCHEMA:
p3-r1-ordinary-nonadmin-principal-evidence/v2
```

The new evidence root itself is the protected top-level anchor. It must be
created once with a protected DACL **at create time**, never created with default
inheritance and repaired later.

Trusted security writers are limited to:

```text
exact P3-R1 creator SID ...-1005
BUILTIN\Administrators  S-1-5-32-544
NT AUTHORITY\SYSTEM     S-1-5-18
```

Ordinary users, Trading, the future test principal, Authenticated Users,
BUILTIN\Users, Codex sandbox identities, and unresolved SIDs are not retained
evidence writers.

The new cross-run root contract also binds:

```text
fixed/local NTFS volume
volume GUID + serial
parent namespace authority
root file identity
exact owner
semantic protected DACL
reparse-point absence
resolved final path
```

A pre-created fixed v2 name is fail-closed denial of service: STOP, never adopt,
delete, repair, rename, retry, or select another suffix.

The separate KSP evidence root remains unchanged:

```text
F:\AI\p3-r1-ksp-disposable-test-v1
```

Architecture 100 authorized and executed **no Windows filesystem, ACL, account,
group, password, KSP, recovery, provider, or production effect**.

---

## 9. Immediate next milestone

Next is a bounded **Codex Sol High** source-only Architecture-100 correction of
the disabled ceremony helper. Sol High is required because this is native Windows
security/authority work involving security descriptors, ACL interpretation,
namespace authority, volume/file identities, handle continuity, and crash/re-entry
semantics.

Allowed implementation files:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Required implementation changes:

1. replace the retired v1 root/schema constants with Architecture-100 v2;
2. construct the exact protected root security descriptor at create time;
3. validate owner, DACL protection, canonical trusted writer semantics, and reject
   extra/untrusted writer authority;
4. implement fixed-volume and parent `FILE_DELETE_CHILD`, `WRITE_DAC`, and
   `WRITE_OWNER` gates;
5. preserve the existing no-delete-share in-run guards;
6. strengthen process re-entry with exact frozen volume/root identity;
7. update strict v2 root-identity evidence and loader validation;
8. keep `ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` and all password/account/group
   paths unreachable by ordinary invocation/tests; and
9. add focused tests for unsafe parent delete-child authority, de-protected/wrong
   DACL, wrong owner, extra ACEs, wrong volume/file identity, reparse
   substitution, pre-created-name collision, uncertain create, and successful
   protected-root inheritance.

Do not touch production files, KSP harness source, recovery key material,
provider code, unrelated subsystems, or retained Windows evidence.

Codex runs focused tests/checks only. ChatGPT reviews the exact GitHub source diff
before the user runs broad/full local certification.

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

After corrected helper source acceptance, the expected chain is:

```text
focused implementation verification
-> ChatGPT exact GitHub diff acceptance
-> broad local source certification
-> restart the complete read-only Architecture-100 readiness freeze from gate #1
-> freeze current volume/root-parent observations
-> separate explicit one-time effect authorization
-> create protected evidence root/account ceremony
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
