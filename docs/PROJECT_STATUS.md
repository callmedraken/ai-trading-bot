# Project Status and Roadmap

This is the canonical high-level project status for AI Trading Bot. Detailed subsystem contracts remain in `docs/architecture/` and `docs/validation/`; the canonical cross-chat resume document is `docs/AI_TRADING_BOT_HANDOFF.md`.

## Product objective and deployment profile

Build a conservative automated trading platform for a **closed, single-owner personal Windows desktop**, progressing through deterministic research, supervised simulated paper, unattended simulated paper, broker-paper, long paper soak, live-readiness review, tiny restricted live operation, and a polished GUI.

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

Architecture 102 freezes the personal-desktop threat model. The owner/Administrator, Windows kernel/boot chain, SYSTEM, and physical control are trusted. The application still protects against practical ordinary-process/configuration/credential/state/duplicate-effect/risk-bypass/recovery failures. The high-assurance hostile-local-admin line is preserved but is no longer a blocker for the single-owner desktop roadmap.

## Primary development line

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
```

Accepted Architecture-94 P2 product checkpoint:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
```

Primary product branch:

```text
feature/personal-desktop-paper-runtime
base: a810122a96b6fc90da25d71eede8da64b7272c98
```

Dedicated local worktree:

```text
F:\AI\worktrees\ai-trading-bot-personal-desktop
feature/personal-desktop-paper-runtime
```

Personal-desktop docs checkpoints:

```text
Architecture 102 adoption: fab1d776abcdcbf09fb26a257ea7fc86f6201b26
Architecture 103 + validation plan: 12e41c4e407a79d63ea896773bf8462038ebba27
```

Accepted/certified PD1 source checkpoints:

```text
PD1A pure authority/bundle:
  fa16eef106638e5d6441a05b7f0dd5f757a63e53

PD1B read authority/security:
  1390a16be5f16f7f38757c875a4648f7ef414d70
  tree 0e9942f293136e9fd6f3bb5c145ada42800608a6

PD1C final accepted source / PD1 certified source:
  e7c2ccbc21972f28b0e82622b426459c67b8007c
  tree d14a986f63a600a8b17bef37c56df332c3b3b88c
```

```text
PD1_SOURCE_ACCEPTED = YES
PD1_SOURCE_CERTIFIED = YES
```

## Mandatory personal-desktop security baseline

The roadmap pivot reduces ceremony depth, not material trading safety. Mandatory controls remain:

- operational trading runs under the existing dedicated non-admin `Trading` account;
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

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider effects are consumed. Call #5 is permanently `FAILED / CONFIRMED`. Call #6 is permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. Provider call #7 is not authorized.

Selected call #6:

```text
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
```

Production identities/paths:

```text
host: DESKTOP-I4DOKM7
creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
runtime: F:\AITradingBot\runtime\python.exe
production temp: F:\AITradingBot\temp
authority DB: F:\AITradingBot\Authority\authority.sqlite3
credential policy: windows-credential-manager-alpaca-market-data/v2
```

## Architecture 94 accepted product work

```text
P1 pure strategy history / deterministic strategy plan: ACCEPTED
  1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority: ACCEPTED
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

## Architecture 103 — personal-desktop paper-account authority v2

Design and validation plan:

```text
docs/architecture/103-personal-desktop-paper-account-authority-v2.md
docs/validation/personal-desktop-paper-account-authority-v2-plan.md
```

### Fixed v2 paths

```text
final authority root:
  F:\AITradingBot\Paper-v2

provisioning staging root:
  F:\AITradingBot\.Paper-v2.provisioning

Architecture-67 operation root:
  F:\AITradingBot\Paper-v2\runtime

operation receipt parent:
  F:\AITradingBot\Paper-v2\runtime\paper-operations
```

### Identity and opening state

```text
anchor schema: personal-desktop-paper-account-authority/v1
layout:        personal-desktop-paper-layout/v1
manifest:      personal-desktop-paper-account-provisioning/v1
UUID5 ns:      022bbd87-6bea-5fd0-a323-5fa355616643
```

The first v2 account is fresh simulated cash-only state:

```text
starting cash: explicit positive Decimal, no code default
positions: none
realized P&L: 0
open orders: none
application metadata: empty
GENESIS as_of: exact verified captured_at of accepted selected C3 call #6
```

Exact starting cash remains deliberately unselected until PD1E.

### Accepted PD1 implementation

PD1A provides the deterministic v2 account ID, strict canonical anchor/manifest models, exact Architecture-61 GENESIS reuse, explicit positive `Decimal` starting cash, and preserved C1/P2 provenance with no filesystem/provider effect.

PD1B provides:

- exact native Trading-token observation with primary/non-elevated/no-thread-impersonation/no-enabled-Administrators requirements and no LSA dependency;
- source-owned fixed v2 paths and bounded no-follow pinned reads;
- role-based v2 ACL verification without modifying the existing C1 policy;
- full installed-account reconstruction through existing Architecture-61/66/67 verification;
- unique graph-derived terminal selection, receipt replay, historical snapshot/configuration dependency verification, and identity/security/content/inventory drift checks.

PD1C provides:

- a production-disabled publisher and isolated disposable publication harness;
- create-new staging, exact staged verification, same-parent no-clobber rename, final reopen/reverification, and four-state crash classification;
- no automatic cleanup/retry after ambiguous publication failure;
- immutable source-owned `PersonalDesktopPaperPublicationFreeze` contract;
- corrected separation between the Trading runtime authority plane and Administrator publication evidence plane.

The accepted authority split is:

```text
Trading / non-admin plane
  genuine process-local ValidatedProductionAuthority + P2
  -> prepares/contextually verifies exact bundle during readiness

Administrator publication plane
  complete Administrator C1 installation-conformance evidence
  + later reviewed source-owned PD1E publication freeze
  -> publication
```

`ValidatedProductionAuthority` and the P2 permit are never serialized or transferred into the Administrator process.

Current certified production source state remains:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE = None
```

No production v2 publication occurred during PD1 source implementation/certification.

### PD1 certification evidence

Focused implementation evidence includes:

```text
PD1B initial focused/regression set: 553 passed
PD1B parent-policy correction set: 244 passed
PD1C corrected focused set: 175 passed
PD1A/PD1B/C1 regressions with PD1C correction: 513 passed
```

Broad PD1D certification at the exact certified commit/tree:

```text
4117 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (417 files already formatted)
git diff --check: PASS
final HEAD/tree: exact
final worktree status: clean
```

A standalone shell source-provenance closeout command later hit PowerShell/Python quoting issues; that harness failure is not a repository/test failure and does not invalidate the accepted full-suite evidence. The full pytest run used the personal-desktop worktree as its repository root and all source/static gates passed.

## Retained failed v1 publication

Historical state remains frozen:

```text
F:\AITradingBot\Paper                       expected absent
F:\AITradingBot\.Paper.provisioning-v1     retained historical staging
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

The ordinary account may receive `AccessDenied` while observing the governed production namespace. `AccessDenied` must not be interpreted as proof of absence. Never rerun the old publisher or delete/repair/rename/migrate/reuse the retained v1 staging tree.

## High-assurance P3-R1 line — preserved, parked, optional

```text
branch: feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
Architecture-101 source-certified commit: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
Architecture-101 source-certified tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
```

Architecture 101 remains blocked only for the parked high-assurance profile because Performance Log Users (`S-1-5-32-559`) holds `SeBatchLogonRight`.

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

## Revised primary roadmap

```text
PD0  personal-desktop profile adoption                     COMPLETE
PD1  personal-desktop paper-account authority v2           CURRENT
  PD1A pure anchor/account-ID/provisioning bundle           ACCEPTED
  PD1B Windows read-only authority + token/ACL/path         ACCEPTED
  PD1C disabled publisher + disposable publication tests   ACCEPTED
  PD1D exact diff review + broad source certification      COMPLETE
  PD1E production readiness / exact bundle freeze          NEXT
PD2  reliable supervised manual paper cycle
PD3  supervised crash/recovery validation
PD4  unattended simulated paper under Trading
PD5  broker-paper integration
PD6  broker-paper soak / operational hardening
PD7  personal-desktop live-readiness
PD8  tiny restricted live -> gradual maturity
```

### PD1E next milestone

PD1E is a readiness/freeze checkpoint, **not publication**. It will:

- select the explicit simulated starting cash;
- use the already accepted call-#6/P2 chronology;
- generate and freeze exact GENESIS, anchor, and provisioning-manifest bytes/hashes/lengths;
- freeze exact `PersonalDesktopPaperPublicationFreeze` values;
- prove current Administrator C1 readiness and fixed-parent/occupancy readiness;
- review the tiny future source freeze/enablement diff separately;
- require a separate explicit user authorization before any production publication effect.

## Effect authorization state

Still **NOT AUTHORIZED**:

```text
retained v1 staging delete/repair/rename
old publisher rerun
Paper-v2 or .Paper-v2.provisioning creation/mutation
production paper-state mutation
production ACL mutation
account/group/password changes
LSA policy/right changes
KSP key/signature/private-export effects
provider call #7
broker order submission
live trading
```

## Workflow invariants

- ChatGPT/Sol owns architecture/security review, exact GitHub diff review, test gates, merge/deployment/production decisions, and next milestones.
- **Tiny scoped status/handoff/docs closeouts are handled directly by ChatGPT by default; do not delegate them to Codex unless there is a concrete reason.**
- Codex handles bounded implementation and may, when explicitly authorized, exact-file stage/commit/ordinary-push after focused gates pass.
- Never `git add .` or `git add -A`.
- Worktree/branch/HEAD mismatch is a STOP; do not self-correct it.
- Controlled Windows pytest uses fresh external `F:\AI\temp\pytest\<unique>` and normally `-p no:cacheprovider`.
- Preserve historical inaccessible caches and unrelated generated/untracked reports.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without explicit approval.

## Documentation workflow

At accepted checkpoints update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Small milestone/status/handoff documentation updates are a ChatGPT-direct task by default. Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only when the reusable workflow rule itself actually changes.
