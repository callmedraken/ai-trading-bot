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
Architecture-100 source-certified checkpoint: 8cfbbd3a30eb704e6acfc1866bf2ed752879e231
Architecture-100 source-certified tree: fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
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

The first disabled/source-only helper checkpoint was:

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

### Architecture 100 — SOURCE CERTIFIED

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

The accepted source implementation checkpoint is:

```text
8cfbbd3a30eb704e6acfc1866bf2ed752879e231
test: implement protected P3-R1 ceremony evidence root

tree: fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
```

The source change remained limited to the existing ceremony helper, wrapper, and
focused tests. It implements create-time protected-DACL construction, exact
owner/protection/ACE validation, parent namespace replacement-authority checks,
fixed NTFS volume/root identity binding, reparse-safe/no-delete-share continuity,
strict v2 retained root identity, and fail-closed collision/uncertain-create
handling. The separate KSP evidence root remains unchanged.

`ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` remains hard-coded. No password
prompt, evidence-root creation, ACL mutation, account/group mutation, KSP effect,
production recovery, signing effect, or provider effect was authorized or run.

Source certification evidence:

```text
focused Architecture-100 helper gate: 47 passed
broad repository run: 3862 passed before legacy harness cache failures
legacy-harness recovery: 758 passed
Ruff check: passed
Ruff format check: passed
git diff --check: passed
final reviewed HEAD/tree: unchanged exact
final P3-R1 worktree: clean
```

The broad-run failures were classified as environment-invalid legacy harness
scratch failures: the two unchanged Architecture-77 authority test modules use a
hard-coded worktree `.pytest_cache` lifecycle-arbiter root that was inaccessible
in this P3-R1 worktree. Those exact unchanged test blobs were rerun from the
validated integration harness while `PYTHONPATH` and printed module `__file__`
provenance proved imports came from the exact reviewed P3-R1 source; the entire
legacy slice then passed 758/758. No full-suite rerun is required unless source
changes.

## Immediate next milestone — read-only execution-readiness restart

Architecture 100 source work is complete. The next substantive milestone is to
restart the complete P3-R1 execution-readiness sequence from **gate #1** rather
than resume the earlier stopped run.

The restart is read-only. It must freshly prove/freeze at least:

1. exact worktree, branch, source commit/tree, helper/wrapper/test hashes, and
   source-enablement diff;
2. exact absence of the retired v1 evidence root and the new v2 evidence root;
3. current `F:\` fixed/local NTFS volume GUID/serial and persistent-ACL support;
4. current `F:\` owner/DACL semantics, no reparse traversal, and no untrusted
   `FILE_DELETE_CHILD`, `WRITE_DAC`, or `WRITE_OWNER` authority capable of
   replacing the protected child;
5. exact creator/Trading identities and expected built-in group SID mappings;
6. candidate-name absence and special-group topology relevant to
   `P3R1KspTestUser`;
7. current password/account/logon policy needed by the one-shot account ceremony;
8. exact Windows PowerShell 5.1, helper, Git, and `netapi32.dll` identities; and
9. confirmation that every effect gate remains disabled before any later
   authorization discussion.

Changed, missing, ambiguous, or unexpectedly writable observations are a STOP.
Do not repair F:\, F:\AI, historical cache state, retained production staging, or
any candidate root merely to make readiness pass.

The later execution authorization, if readiness succeeds, must also treat root
creation as one-shot across process loss: once an authorized create may have
begun, an ambiguous process termination consumes that authorization and permits
only read-only reconciliation, never blind relaunch/retry.

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

Required order from the source-certified checkpoint is:

```text
complete read-only Architecture-100 readiness restart from gate #1
-> ChatGPT acceptance of frozen readiness evidence
-> separate explicit one-time filesystem/account effect authorization
-> protected evidence-root/account ceremony
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
- when an unchanged legacy harness hard-codes inaccessible `.pytest_cache`
  scratch, use the validated clean-harness/provenance method rather than repairing
  retained cache state;
- under Windows PowerShell 5.1, prefer piping a here-string to Python stdin for
  quoting-sensitive provenance snippets instead of `python -c`;
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
