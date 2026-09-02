# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot.
The canonical cross-chat handoff is `docs/AI_TRADING_BOT_HANDOFF.md`; detailed
architecture/validation documents remain authoritative for subsystem contracts,
evidence, and historical decisions.

## Long-term objective

Build a conservative automated trading platform that progresses safely through
historical research, deterministic simulation, manual paper, unattended paper,
long paper soak, broker-paper, live-readiness certification, tiny restricted
live operation, mature automated operation, and a polished end-user GUI.

**Production/live trading: NO-GO.** Live trading remains unavailable until the
separately reviewed brokerage, reconciliation, credential, operating-mode,
operator-control, long-soak, and live-readiness gates are complete.

## Current repository and worktree state

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
docs: repair integrated GUI status
```

Current P3-R1 development context:

```text
worktree: F:\AI\worktrees\ai-trading-bot-p3-r1
branch: feature/p3-r1-recovery-implementation
Architecture-100 docs checkpoint: e2861fab3af7d297d79274db2a82fd134672fb58
Architecture-100 tree: d6f9203184d90a0c409d929c25bb2c7e7e520f29
```

The main `F:\AI\ai-trading-bot` worktree remains the GUI worktree and must not
be reused for P3-R1 implementation. The integration worktree remains
`F:\AI\ai-trading-bot-integration`. Preserve unrelated generated/untracked
reports and historical pytest evidence.

## C3 — FULLY COMPLETE / ACCEPTED

C1 `ValidatedProductionAuthority` and C2 `WindowsTransactionalAuthority` are the
reviewed authority foundations. C3 is the reviewed bridge into real market-data
credentials, isolated native Windows child execution, Alpaca transport, parent
verification, final-artifact publication, terminal evidence, and durable
selection.

Accepted C3 production release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains
`FAILED / CONFIRMED` and permanently non-retryable. Call #6 remains
`SUCCEEDED / CONFIRMED` and `SUCCESS_SELECTED`; its provider effect must never be
rerun. No provider call #7 is authorized. `/v2` Alpaca credential references are
immutable historical state; later rotation requires a separately reviewed `/v3`
or later version.

## Architecture 94 manual paper cycle

Architecture 94 remains simulated paper only. It does not authorize a broker,
live trading, unattended scheduling, automatic retry, or another C3 provider
effect.

### P1 — ACCEPTED

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

P1 remains the pure deterministic strategy-history/plan boundary.

### P2 — FULLY ACCEPTED

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

P2 remains the genuine C1-attenuated, read-only selected-C3 authority boundary.
The one supervised production P2 reread of already-durable successful call #6
passed and **must not be rerun**.

## P3 / P3-R1 retained production state

Frozen production paths and identities remain:

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production temp: F:\AITradingBot\temp
Authority DB: F:\AITradingBot\Authority\authority.sqlite3
Capture output: F:\AITradingBot\Authority\capture-output
Paper final root: F:\AITradingBot\Paper
Paper retained staging root: F:\AITradingBot\.Paper.provisioning-v1
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

The original Administrator paper-root publication attempt remains retained and
must not be rerun. Read-only recovery forensics established:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
production authority DB: unchanged exact
```

Architectures 95 and 96 remain the retained-staging recovery and signed recovery
authorization contracts. Architectures 97 through 100 now define the additional
recovery-signing/KSP-validation path needed before recovery execution can be
trusted.

## Architectures 97–100 — current security checkpoint

Relevant contracts:

```text
docs/architecture/97-p3-r1-recovery-signing-trust-reestablishment.md
docs/architecture/98-p3-r1-ksp-machine-key-security-contract.md
docs/architecture/99-p3-r1-ordinary-nonadmin-test-principal.md
docs/architecture/100-p3-r1-protected-account-ceremony-evidence-root.md

docs/validation/p3-r1-ordinary-nonadmin-test-principal-creation-ceremony.md
docs/validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md
docs/validation/p3-r1-ksp-disposable-test-harness.md
```

Architecture 99 freezes a dedicated ordinary non-admin local test identity named
`P3R1KspTestUser`. Windows must supply its SID after a separately authorized
create-new ceremony. The account may never become production, Trading, recovery,
signing, KSP-owner/ACE, or Credential Manager authority.

The account-creation procedure is documentation-complete at:

```text
022960a3f242ded927edf3ae4667f87e724aeb19
docs: define P3-R1 test-user creation ceremony
```

The first disabled/source-only helper checkpoint is:

```text
d509537b88f66ef244d326e5417d38d9e5f25f53
test: add disabled P3-R1 test-user ceremony helper
```

It added only:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

The helper keeps `ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false`; ordinary invocation
cannot prompt for a password or cross the account/group mutation boundaries.

### Architecture 100 — ACCEPTED DOCS-ONLY DESIGN

A read-only ACL/namespace diagnostic invalidated the old retained-evidence
location under `F:\AI`: untrusted principals had enough authority on that
ancestor to defeat the strict cross-run pathname-integrity requirement after
no-delete-share guards were released.

Architecture 100 supersedes only the account-ceremony evidence-root location,
schema, and inherited-security assumption. The old location is retired before
any effect occurred:

```text
retired: F:\AI\p3-r1-ordinary-nonadmin-principal-v1
new:     F:\p3-r1-ordinary-nonadmin-principal-v2
schema:  p3-r1-ordinary-nonadmin-principal-evidence/v2
```

The new top-level evidence root must be created once with a protected DACL at the
successful create operation, not created permissively and repaired afterward.
The reviewed security-writer set is limited to the exact P3-R1 creator,
BUILTIN\Administrators, and SYSTEM. Ordinary users receive no evidence-root ACE.

Architecture 100 also requires fresh parent/volume authority proof, persistent
root identity binding, reparse-safe reopen, exact owner/protected-DACL
validation, and fail-closed handling of a pre-created fixed name. The separate
KSP evidence root remains unchanged.

**No Windows filesystem/account/group/password/KSP effect was authorized or run
by Architecture 100.**

## Immediate next implementation checkpoint

The next task is a bounded **Codex Sol High** source-only correction from the
exact current P3-R1 branch checkpoint. Sol High is required because the change
involves native Windows security descriptors, ACL semantics, namespace authority,
volume/file identity, handle continuity, and crash/re-entry behavior.

Scope is limited to the existing disabled ceremony helper/wrapper and focused
tests:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

The correction must:

1. replace the retired v1 root/schema with the exact Architecture-100 v2 values;
2. construct the protected root security descriptor at create time;
3. validate exact trusted owner/protected DACL and reject extra/untrusted writer
   authority;
4. implement the fixed-volume and parent `FILE_DELETE_CHILD` / `WRITE_DAC` /
   `WRITE_OWNER` gates;
5. preserve the existing in-run no-delete-share guards and strengthen cross-run
   volume/root identity continuity;
6. freeze/validate the v2 root-identity evidence schema;
7. keep all password/account/group effects unreachable by default; and
8. add focused fake/native-model tests for wrong parent authority, DACL
   de-protection, wrong owner, extra ACEs, wrong volume/file identity, reparse
   substitution, collision, uncertain create, and protected inheritance.

Do not modify production files, KSP harness source, provider code, recovery key
material, unrelated subsystems, or historical retained evidence.

Codex should run focused tests/checks only while iterating. Full repository or
long integration/E2E certification remains a later local user gate after ChatGPT
accepts the exact source diff.

## Effect authorization state

Still **NOT AUTHORIZED**:

- evidence-root creation or ACL mutation;
- password prompting or capture;
- `P3R1KspTestUser` creation, reset, deletion, rename, or enable/disable;
- local-group add/remove effects;
- KSP native effect execution or cleanup;
- recovery signing/private-key effects beyond already accepted retained state;
- production P3 recovery;
- provider call #7;
- broker/live trading; and
- P4/P5/P6 external effects.

After corrected helper source acceptance, the required order is:

```text
focused source verification
-> ChatGPT exact GitHub diff acceptance
-> broader local source certification
-> restart complete read-only Architecture-100 readiness freeze from gate #1
-> separate explicit effect authorization
-> account/root ceremony
-> genuine ordinary-user qualification
-> later KSP SID/source freeze and denial experiment
-> recovery path only after all independent recovery gates are accepted
```

## GUI status

GUI-A1 through GUI-A7 remain fully accepted and integrated. GUI capabilities are
read-only presentation/inspection boundaries and do not own production authority,
credentials, paper-account mutation, retry, recovery, brokerage, or execution.

## Workflow invariants

Canonical workflow rules remain in `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md`:

- prove exact worktree, branch, and HEAD before every bounded Codex task;
- any startup mismatch is a STOP; never self-correct Git state;
- every controlled Windows pytest gate uses a fresh explicit external
  `F:\AI\temp\pytest\<unique-run>` basetemp;
- normally use `-p no:cacheprovider` when cache behavior is irrelevant;
- preserve unrelated generated/untracked reports and historical pytest evidence;
- run focused tests during implementation and reserve full certification for the
  accepted final source tree;
- never merge, rebase, force-push, amend, change PR metadata/review threads, or
  modify unrelated files without explicit approval.

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

Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only when a checkpoint reveals a
reusable workflow rule that is not already captured. Git-tracked documents are
authoritative; uploaded Project copies are context mirrors only.

Documentation closeout does not authorize merge, rebase, force-push, amend,
review-thread resolution, PR metadata changes, production/provider effects, or
unrelated modifications.
