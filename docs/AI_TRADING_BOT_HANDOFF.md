# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Primary product branch:** `feature/personal-desktop-paper-runtime`  
**Primary worktree:** `F:\AI\worktrees\ai-trading-bot-personal-desktop`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded copies are mirrors. Prove the active worktree, branch, HEAD, tree, and clean state before acting.

## 1. Product goal and threat model

Build a conservative automated trading platform for a **closed, single-owner personal Windows desktop**:

**deterministic research → supervised simulated paper → unattended simulated paper → broker-paper → long paper soak → personal-desktop live-readiness → tiny restricted live → mature operation → polished GUI.**

Stable constraints:

```text
US stocks / ETFs
long-only
no margin / leverage / options / shorts / crypto
deterministic risk approval
paper-by-default
complete auditability
```

Architecture 102 trusts the owner/Administrator, Windows kernel/boot/SYSTEM, and physical machine control. The bot still protects against practical ordinary-process/configuration/credential/state/duplicate-effect/risk-bypass/recovery failures. It is not designed to survive malicious local Administrator/SYSTEM/kernel compromise.

The high-assurance Windows line becomes blocking again only if deployment changes to mutually untrusted local users, commercial distribution, third-party funds, regulatory/custody requirements, or hostile-admin resistance.

## 2. Branch/worktree routing

Primary product branch/worktree:

```text
feature/personal-desktop-paper-runtime
base: a810122a96b6fc90da25d71eede8da64b7272c98
F:\AI\worktrees\ai-trading-bot-personal-desktop
```

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
```

Other preserved worktrees/lines may remain active. Do not switch, clean, reset, delete generated artifacts from, or otherwise disturb another active worktree as part of PD2 work.

Before every bounded implementation task, verify:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Any mismatch is a STOP. Do not self-correct with checkout/switch/reset/rebase/clean.

## 3. ChatGPT/Codex workflow

ChatGPT/Sol owns architecture, native Windows security/authority review, exact GitHub diff review, debugging strategy, test/certification gates, merge/deployment/production decisions, and next-step planning.

Current Codex model routing:

```text
tiny/simple                                  -> ChatGPT direct
known contract + known files/test surface    -> Luna Extra High
discovery-aware/cross-module bounded work    -> Astra
native Windows/security/authority/recovery   -> Sol High
```

Use **Luna Extra High** when the contract, entry points, affected files, and focused tests are already known and implementation is localized/mechanical or a small bounded correction.

Use **Astra** when the task remains bounded but the root cause, affected file set, hidden coupling, or cross-module consequences need repository exploration before implementation. Astra is also preferred for bounded refactors/migrations/hygiene/consistency work and explicitly requested broad read-only repository audits. Astra replaces Sol Medium as the normal middle tier for new Codex work.

Use **Sol High** for native Windows/security, production authority, ordering, crash/recovery, credential/reference-version changes, external-effect containment, broker/live boundaries, or other architecture-sensitive implementation where a mistake could weaken a safety invariant.

Sol Medium is no longer part of the default routing ladder; use it only if explicitly requested or Astra is unavailable and the task still fits the former subtle-but-bounded tier.

Model choice does not transfer architecture or acceptance authority. If Astra exploration exposes a need to change the contract or architecture, stop and return that decision to ChatGPT rather than broadening the checkpoint.

Do not use subagents unless explicitly requested.

Codex is the bounded implementation agent. It should read `AGENTS.md`, `docs/PROJECT_STATUS.md`, and only relevant architecture/validation documents; run focused tests/checks; preserve unrelated generated/untracked files; and stop before broad certification unless explicitly told otherwise.

When a checkpoint explicitly authorizes commit/push, Codex may exact-file stage the intended paths, verify the staged filename set and `git diff --cached --check`, make a normal commit, and ordinary-push the isolated feature branch. Never use `git add .` or `git add -A`.

No amend/rebase/merge/force-push/PR-metadata/review-thread changes without explicit approval.

Controlled Windows pytest uses:

```text
--basetemp F:\AI\temp\pytest\<fresh-unique>
-p no:cacheprovider
```

unless cache behavior itself is under test.

Focused tests belong in the implementation loop. Broad/full repository suites, long integration/E2E gates, deployment, and operator Windows gates are normally run locally by the user only at the certification boundary ChatGPT identifies.

## 4. Standing authorization model

The user has authorized automatically continuing to the next best scoped checkpoint when the preceding reviewed checkpoint passes.

That standing authorization applies only within the already-reviewed PD1/PD2 development sequence when the next action is clearly safe and bounded. It does **not** automatically authorize:

```text
provider call #7
broker submission
live trading
unattended scheduling
v1 cleanup/repair/migration
account/group/password changes
LSA policy/right changes
KSP/signing/private-export effects
unrelated project effects
merge/rebase/amend/force-push/PR metadata changes
```

## 5. Frozen C3 production state

Accepted C3 release source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six authorized real-provider effects are consumed. Call #5 is permanently `FAILED / CONFIRMED`. Call #6 is permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. Provider call #7 is not authorized.

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Host/deployment facts:

```text
host: DESKTOP-I4DOKM7
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
creator/John SID ending: -1005
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
runtime: F:\AITradingBot\runtime\python.exe
authority DB: F:\AITradingBot\Authority\authority.sqlite3
credential policy: windows-credential-manager-alpaca-market-data/v2
```

## 6. Architecture 94 accepted product work

```text
P1 pure strategy history / deterministic strategy plan
  1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority
  a810122a96b6fc90da25d71eede8da64b7272c98
```

Preserve this composition:

```text
selected verified C3 snapshot
+ explicit deterministic strategy history
+ authoritative paper-account tip
-> deterministic strategy plan
-> planner / proposal
-> deterministic portfolio risk
-> simulated paper execution
-> successor checkpoint + full-lineage verification
-> Architecture-67 durable transition + receipt
```

## 7. Architecture 103 deployment model

Architecture 103 is the personal-desktop Paper-v2 authority. Fixed paths:

```text
final authority root:       F:\AITradingBot\Paper-v2
provisioning staging root:  F:\AITradingBot\.Paper-v2.provisioning
A67 operation root:         F:\AITradingBot\Paper-v2\runtime
receipt parent:             F:\AITradingBot\Paper-v2\runtime\paper-operations
```

The retained failed v1 state stays separate:

```text
F:\AITradingBot\Paper                     ABSENT
F:\AITradingBot\.Paper.provisioning-v1   PRESENT / RETAINED / UNTOUCHED
```

Never rerun the old v1 publisher or delete/repair/rename/migrate/reuse the v1 staging tree as incidental cleanup.

The accepted authority split remains:

```text
Trading runtime plane
  genuine process-local ValidatedProductionAuthority + P2
  -> exact read/verification authority

Administrator publication plane
  complete Administrator C1 installation-conformance evidence
  + source-owned PersonalDesktopPaperPublicationFreeze
  -> one-time publication admission
```

A Trading runtime capability/P2 permit is never transferred into Administrator. The publication freeze is immutable reviewed data, not a runtime capability.

## 8. PD1 final state — COMPLETE

Canonical completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
commit c26a9b5333d62967e574de89a2ae5fd966594abd
```

Final accepted PD1 production-read correction:

```text
commit a353d58230b5b37231d00e7799fa828ddf31bf30
tree   db750395e9a4a837269c1b93befea453ed604380
message fix: admit protected paper parent runtime
```

Canonical status:

```text
PD1_ARCHITECTURE_ACCEPTED    = YES
PD1_SOURCE_ACCEPTED          = YES
PD1_SOURCE_CERTIFIED         = YES
PD1_PRODUCTION_READY         = YES
PD1_V2_PUBLISHED             = YES
PD1_TRADING_RUNTIME_VERIFIED = YES
PD1                          = COMPLETE
```

Exact published account:

```text
paper_account_id:     9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint:   1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:        Decimal("25000")
GENESIS as_of:        2026-08-29T09:46:43.769105+00:00
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
Trading SID:          S-1-5-21-1397534616-3988210162-180023805-1009
```

Frozen artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
freeze Git blob b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

Durable occupancy:

```text
F:\AITradingBot\Paper-v2                    PRESENT / VERIFIED
F:\AITradingBot\.Paper-v2.provisioning      ABSENT
F:\AITradingBot\Paper                       ABSENT
F:\AITradingBot\.Paper.provisioning-v1      PRESENT / RETAINED / UNTOUCHED
```

Both source effect gates are contained:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

### PD1E production/recovery history

```text
PD1E-D source-bound Administrator admission             PASS
PD1E-E publication source enablement                    ACCEPTED
  f4a3a697d2c35cd1efee1037862297e76c80161e

PD1E-F original production publication                  CONSUMED / BLOCKED
  failure phase: staged-verify
  v2 final absent / v2 staging present

read-only forensic qualification                        EXACT CANDIDATE

PD1E-FR1 publication parent/provenance correction       ACCEPTED
  c71147e62858fb0e494828efb52ab91a78027059
  301ecee4767d035ad032f5bb6e4d81d6e5edb1ce

PD1E-FR2 read-only recovery qualification source        ACCEPTED
  a28c3b8b74c0dc80b07dee1c50735f7998e39b26
PD1E-FR2 real-host qualification                        PASS

PD1E-FR3A recovery finalizer source                     ACCEPTED
  3cfc9e8aa8f6d25590abdfc82f6617a52e18dbf2

PD1E-FR3B recovery source enablement                    ACCEPTED
  7e616b0ac2a43d59f4b9c0e879cf2bccbd8c9b97

PD1E-FR3C one-shot real-host no-clobber recovery        SUCCESS
  FINALIZED_AND_VERIFIED / COMPLETE
  exit code 0

PD1E-FR3C-R1 immediate recovery re-containment          ACCEPTED
  085ddfc0852d7d23eaba93f41cfcb3247db28537
  both effect gates False

initial FR3D genuine Trading read                       BLOCKED
  genuine Trading C1 acquisition passed
  protected-parent source/design mismatch exposed

PD1E-FR3D-R1 protected-parent runtime correction        ACCEPTED
  a353d58230b5b37231d00e7799fa828ddf31bf30

final FR3D genuine Trading-account verification         PASS
```

The FR3D-R1 root cause was a source/design mismatch, not a host ACL defect. `F:\AITradingBot` intentionally remains Administrator/SYSTEM-only. Trading does not enumerate or pin that protected parent; it uses a source-owned fixed-name zero-access/no-follow staging probe and opens `Paper-v2` directly, while preserving strict root/anchor/GENESIS/runtime/lineage verification.

### Final PD1 certification

At accepted source `a353d582...` / tree `db750395...`:

```text
4686 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (402 files)
git diff --check: PASS
worktree: clean
```

Genuine non-admin Trading verification also passed with exact SID `-1009`, `IS_ADMIN=False`, exact paper account/GENESIS, `$25,000` starting cash, zero lineage edges/successors/reports/snapshots/receipts, fixed operation root, both effect gates false, and exit code 0.

## 9. Current milestone — PD2A already authorized

PD2 is reliable supervised manual paper operation. The first slice is source-only and must perform **no production paper-state mutation**.

PD2A objective:

```text
source-only account-scoped Windows mutex
+ supervised paper-cycle admission contract
```

Why first: Architecture 103 requires one account-scoped exclusive Windows mutex before any mutation under `Paper-v2\runtime`. It must be held from authoritative account inspection through execution, Architecture-67 transition commitment, and receipt commitment/recovery.

Existing `GlobalLifecycleMutex` is useful conceptually but is not directly suitable because its identity is tied to C3 lifecycle reservations and it waits indefinitely.

### PD2A mutex identity

Source-owned contract:

```text
label  = personal-desktop-paper-account-mutex/v1
prefix = Global\AITradingBot-PaperAccount-v1-
identity material = exact label + canonical paper_account_id only
```

Do not include PID, username, wall clock, random UUID, C3 reservation, current checkpoint, caller path, environment, or configuration values.

Validate `paper_account_id` as exact canonical UUID text before name derivation.

### PD2A kernel security

Target protected DACL:

```text
Administrators: MUTEX_ALL_ACCESS
SYSTEM:         MUTEX_ALL_ACCESS
Trading SID:    MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE
```

Accepted owners are the exact Trading SID when created by Trading, Administrators when created by an explicitly allowed elevated administrative/diagnostic path, and SYSTEM. Existing mutex objects must have their kernel owner/protected-DACL/exact ACE policy inspected before ownership is accepted.

### PD2A bounded acquisition

No `INFINITE` wait. Use a source-owned deterministic maximum appropriate for one supervised paper cycle; approximately 30 seconds is the working target unless a stronger existing repository convention is found.

Wait semantics:

```text
WAIT_OBJECT_0  -> OWNED
WAIT_TIMEOUT   -> fail closed / busy, no paper effect
WAIT_FAILED    -> fail closed
unknown result -> fail closed
WAIT_ABANDONED -> explicit ABANDONED_OWNER evidence
```

Windows gives ownership on `WAIT_ABANDONED`; retain that fact explicitly. Later PD2 composition must reconcile durable account/receipt state before any new mutation after an abandoned owner. Do not silently collapse it to ordinary ownership.

Suggested immutable acquisition evidence:

```text
paper_account_id
name
digest
state: OWNED | ABANDONED_OWNER
was_abandoned
```

### PD2A lifecycle/non-reentrancy

The mutex scope must close unowned handles on failure, release only when actually owned, close after release, fail closed on `ReleaseMutex` failure while still closing the handle, and clean up on exceptions.

Do not assume Win32's mutex semantics make this non-reentrant. Win32 mutex ownership is recursive for the owning thread, so PD2A must intentionally enforce the source contract that a second active same-account acquisition is rejected rather than relying only on a per-instance `_handle` guard.

### PD2A production admission seam

Production admission must compose:

```text
genuine ValidatedPersonalDesktopPaperAccount
-> exact paper_account_id from registered verified evidence
-> deterministic account mutex acquisition
-> immutable acquisition evidence
```

A low-level pure name-derivation helper may accept canonical `paper_account_id` for tests, but the production composition must not acquire a production mutex from an arbitrary caller UUID.

Important ordering for later PD2 composition:

1. establish genuine C1/Trading paper-account authority and immutable account identity;
2. acquire the account mutex;
3. while the mutex remains held, **reread/revalidate the mutable authoritative lineage/tip** before any transition;
4. future strategy/plan/risk/simulated execution;
5. future Architecture-67 transition commitment;
6. future receipt commitment or zero-runtime recovery/reconciliation;
7. release only after terminal durable outcome/reconciliation.

The pre-mutex authority read is sufficient to establish the immutable account identity used for the mutex, but must not become a stale substitute for the mutable post-acquisition account-state revalidation used by a future writer.

PD2A itself stops before steps 3-6: it must not call the Architecture-67 writer.

### PD2A tests

Use fake native/kernel boundaries. At minimum prove:

```text
deterministic identity and name
malformed/noncanonical account UUID rejection
same account -> same name; different account -> different name
caller cannot supply production mutex name
production wait is bounded and never INFINITE
WAIT_OBJECT_0 -> OWNED
WAIT_TIMEOUT / WAIT_FAILED / unknown -> fail closed
WAIT_ABANDONED -> explicit ABANDONED_OWNER
exact existing kernel ACL/owner validation
Trading/Admin/SYSTEM reviewed owners accepted; outsiders rejected
cross-instance same-thread same-account reentrant acquire rejected
failure cleanup closes handle
release only when owned
ReleaseMutex failure fails closed while handle still closes
normal/exception context-manager cleanup
production admission requires genuine validated paper-account authority
mutex identity comes from that authority's exact paper_account_id
no Architecture-67 write
no production filesystem mutation
both existing effect gates remain False
publication freeze unchanged
```

If useful, one disposable opt-in native Windows mutex integration test may use a test-only name that cannot collide with production. Do not create/open the production paper-account mutex during PD2A verification.

Likely new source:

```text
src/trading_bot/runtime/personal_desktop_paper_account_mutex.py
```

A separate small supervised-admission module is acceptable if cleaner. Reuse reviewed security/kernel helpers only where their contracts fit; do not repurpose `GlobalLifecycleMutex` in place.

## 10. Architecture-67 ordering context for future PD2

Architecture 67 already defines the restart-safe paper-operation transition and receipt machinery. Preserve these facts when composing PD2 after PD2A:

- a finalized transition directory is the authoritative account-state commit point;
- prospective successor edge and full lineage must verify before transition publication;
- staged and finalized transition bytes are reread and reverified;
- receipt commitment occurs only after the committed transition rereads and verifies;
- a crash after transition finalization but before receipt finalization may use the existing zero-runtime receipt-recovery path when exact read-only reconciliation proves the required state;
- receipt staging, invalid transition/receipt evidence, or dependency mismatch blocks and is preserved rather than repaired/retried automatically;
- deterministic failed receipts are separate from filesystem/permission/ambiguity failures.

The PD2 account mutex must eventually span this whole critical section through receipt commitment or reconciliation, not merely strategy execution or transition computation.

## 11. Current roadmap

```text
PD0  personal-desktop profile adoption                     COMPLETE
PD1  personal-desktop paper-account authority v2           COMPLETE
PD2  reliable supervised manual paper cycle                CURRENT
  PD2A account-scoped Windows mutex + admission contract   AUTHORIZED / NEXT
  PD2B supervised composition                              NOT YET AUTHORIZED
  first real Paper-v2 runtime mutation                     NOT YET AUTHORIZED
PD3  supervised crash/recovery validation
PD4  unattended simulated paper under Trading
PD5  broker-paper integration
PD6  broker-paper soak / operational hardening
PD7  personal-desktop live-readiness
PD8  tiny restricted live -> gradual maturity
```

## 12. Still NOT authorized

```text
provider call #7
broker order submission
live trading
unattended scheduling
old v1 publisher rerun
v1 staging delete/repair/rename/migration/reuse
Paper-v2 manual mutation outside reviewed PD2 effect checkpoints
account/group/password changes
LSA rights/policy changes
KSP/signing/private-export effects
merge/rebase/force-push/amend/PR metadata changes without explicit approval
```

## 13. Resume procedure

1. Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff, `docs/architecture/103-personal-desktop-paper-account-authority-v2.md`, and `docs/validation/pd1-personal-desktop-paper-v2-completion.md`.
2. For PD2A also read `docs/AI_DEVELOPMENT_WORKFLOW.md`, `src/trading_bot/runtime/windows_authority_mutex.py`, `src/trading_bot/runtime/windows_authority_security.py`, `src/trading_bot/runtime/personal_desktop_paper_account_read_authority.py`, `src/trading_bot/runtime/paper_operation.py`, Architecture 67, and directly associated tests.
3. Prove exact worktree/branch/HEAD/tree/clean state. Never self-correct a mismatch.
4. Continue PD2A with **Codex Sol High** because it is native Windows concurrency/security authority.
5. Keep PD2A source-only: no production paper-state mutation, no real production paper-account mutex acquisition, no provider/broker/live effect.
6. Have Codex run focused tests and changed-file Ruff/diff checks only during implementation and provide the exact commands for the user's later full local certification.
7. When the scoped commit is pushed, ChatGPT reviews the exact GitHub diff before authorizing broader certification or the next PD2 checkpoint.
8. Include the next milestone in every verification/acceptance report.

## 14. Definition of project success

The project is not complete merely when it can place trades. It succeeds when the platform can research deterministically, acquire trusted data safely, apply deterministic risk, interact safely with a brokerage, reconcile external outcomes after failures/restarts, run unattended, fail closed when authority/state is uncertain, expose durable evidence, operate under strict real-money controls, recover predictably, remain understandable/stoppable by its operator, and expose the reviewed system through a polished GUI without giving AI or presentation code alternate authority paths.
