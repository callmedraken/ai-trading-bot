# Project Status and Roadmap

This is the canonical high-level project status for AI Trading Bot. Detailed subsystem contracts remain in `docs/architecture/` and `docs/validation/`; the canonical cross-chat resume document is `docs/AI_TRADING_BOT_HANDOFF.md`.

## Product objective and deployment profile

Build a conservative automated trading platform for a **closed, single-owner personal Windows desktop**, progressing through deterministic research, supervised simulated paper, unattended simulated paper, broker-paper, long paper soak, personal-desktop live-readiness, tiny restricted live operation, and a polished GUI.

Stable product constraints:

```text
US stocks / ETFs
long-only
no margin / leverage / options / shorts / crypto
deterministic risk approval
paper-by-default
complete auditability
```

**Production/live trading remains NO-GO.**

Architecture 102 freezes the personal-desktop threat model. The owner/Administrator, Windows kernel/boot chain, SYSTEM, and physical control are trusted. The application still protects against practical ordinary-process/configuration/credential/state/duplicate-effect/risk-bypass/recovery failures. The preserved high-assurance hostile-local-admin line is not a blocker for the single-owner desktop roadmap.

## Primary development line

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
```

Accepted Architecture-94 P2 product checkpoint:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
```

Primary product branch/worktree:

```text
feature/personal-desktop-paper-runtime
base: a810122a96b6fc90da25d71eede8da64b7272c98
F:\AI\worktrees\ai-trading-bot-personal-desktop
```

Architecture checkpoints:

```text
Architecture 102 adoption:          fab1d776abcdcbf09fb26a257ea7fc86f6201b26
Architecture 103 + validation plan: 12e41c4e407a79d63ea896773bf8462038ebba27
```

## Mandatory personal-desktop security baseline

- steady-state trading runs under the dedicated non-admin `Trading` account;
- market-data/broker/live credentials stay outside source/plain config and use reviewed Windows-backed storage;
- paper is default; future live requires a separate explicit arming boundary;
- every executable order passes deterministic risk authority;
- strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass risk;
- durable state outranks process-local assumptions;
- ambiguous provider/broker effects are reconciled or fail closed rather than blindly retried;
- important runtime/config/state locations are source-governed with practical least-privilege ACLs;
- audit/recovery evidence explains attempts, durable commitments, external responses, and retry safety;
- crash/restart, duplicate invocation, stale input, corruption/conflict, and receipt recovery remain roadmap gates.

## Frozen C3 production state

Accepted C3 release source:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six authorized real-provider effects are consumed. Call #5 is permanently `FAILED / CONFIRMED`. Call #6 is permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. **Provider call #7 is not authorized.**

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Production identities:

```text
host: DESKTOP-I4DOKM7
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
runtime: F:\AITradingBot\runtime\python.exe
authority DB: F:\AITradingBot\Authority\authority.sqlite3
credential policy: windows-credential-manager-alpaca-market-data/v2
```

## Architecture 94 accepted product work

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

## PD1 — personal-desktop paper-account authority v2 — COMPLETE

Canonical completion record:

```text
docs/validation/pd1-personal-desktop-paper-v2-completion.md
commit c26a9b5333d62967e574de89a2ae5fd966594abd
```

Final accepted PD1 production-read source:

```text
commit a353d58230b5b37231d00e7799fa828ddf31bf30
tree   db750395e9a4a837269c1b93befea453ed604380
message fix: admit protected paper parent runtime
```

Canonical PD1 status:

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

Both production effect gates are contained:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

Important production/recovery history:

```text
PD1E-D source-bound Administrator admission         PASS
PD1E-F original production publication              CONSUMED / BLOCKED
PD1E-FR2 read-only recovery qualification            PASS
PD1E-FR3C one-shot real-host recovery                SUCCESS / FINALIZED_AND_VERIFIED
PD1E-FR3C-R1 recovery re-containment                 ACCEPTED
initial FR3D Trading read                            BLOCKED by protected-parent source mismatch
PD1E-FR3D-R1 source correction                       ACCEPTED at a353d582...
final FR3D genuine non-admin Trading verification    PASS
```

The protected-parent correction is a source correction, not a host-ACL relaxation. `F:\AITradingBot` remains Administrator/SYSTEM-only. Trading probes the exact fixed staging sibling without requiring parent enumeration and opens/verifies `Paper-v2` directly through the strict source-owned runtime boundary.

Final PD1 certification at `a353d582...`:

```text
4686 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (402 files)
git diff --check: PASS
worktree: clean
```

The retained failed v1 staging tree is historical evidence. Never rerun the old v1 publisher or delete, repair, rename, migrate, or reuse that tree as incidental cleanup.

## Current milestone — PD2A

PD2 is the reliable supervised manual paper-cycle milestone.

The currently authorized first slice is:

```text
PD2A source-only account-scoped Windows mutex
+ supervised paper-cycle admission contract
```

PD2A performs **no production Paper-v2 mutation**. It establishes concurrency/admission authority only.

Architecture 103 requires one exclusive account-scoped Windows mutex before any Architecture-67 mutation under `Paper-v2\runtime`. The mutex:

- is deterministically derived from the exact canonical `paper_account_id` under a source-owned namespace;
- is never caller-named;
- does not create account authority;
- is acquired only from genuine validated paper-account authority in the production admission seam;
- has a protected reviewed Admin/SYSTEM/Trading kernel DACL;
- uses bounded acquisition, never `INFINITE`;
- fails closed on timeout, wait failure, unknown status, or security mismatch;
- preserves `WAIT_ABANDONED` as explicit `ABANDONED_OWNER` evidence;
- must eventually remain held across authoritative account-state revalidation, strategy/plan/risk/simulated execution, Architecture-67 transition commitment, and receipt commitment/reconciliation.

Proposed source-owned identity contract:

```text
label  = personal-desktop-paper-account-mutex/v1
prefix = Global\AITradingBot-PaperAccount-v1-
identity material = exact label + canonical paper_account_id only
```

Reviewed DACL target:

```text
Administrators: MUTEX_ALL_ACCESS
SYSTEM:         MUTEX_ALL_ACCESS
Trading SID:    MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE
protected DACL
```

A small deterministic production wait bound such as 30 seconds is the working target unless implementation discovers a stronger already-reviewed repository convention.

PD2A must not call the Architecture-67 writer and must not create/open the real production paper-account mutex during ordinary unit verification. Fake native/kernel boundaries are the default; an optional disposable native integration test must use a test-only name that cannot collide with production.

## Primary roadmap

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

## Still not authorized

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

## Workflow invariants

- ChatGPT/Sol owns architecture/security review, exact GitHub diff review, test gates, merge/deployment/production decisions, and next milestones.
- Tiny scoped status/handoff/docs closeouts are handled directly by ChatGPT by default.
- Codex handles bounded implementation. Model routing: Luna Extra High for localized/mechanical/frozen-contract work; Sol Medium for subtle bounded deterministic work; Sol High for native Windows/security/authority/order/crash/recovery work.
- Codex runs focused tests/checks during iteration; broad/full certification is normally run locally by the user at the final gate.
- Never `git add .` or `git add -A`; exact-file stage only.
- Worktree/branch/HEAD mismatch is a STOP; do not self-correct with checkout/switch/reset/rebase/clean.
- Controlled Windows pytest uses fresh external `F:\AI\temp\pytest\<unique>` and normally `-p no:cacheprovider`.
- Preserve historical inaccessible caches and unrelated generated/untracked reports.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without explicit approval.

## Documentation workflow

At accepted checkpoints review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Small milestone/status/handoff documentation updates are a ChatGPT-direct task by default. Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only when the reusable workflow rule itself changes.
