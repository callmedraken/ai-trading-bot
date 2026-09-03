# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**Primary product branch:** `feature/personal-desktop-paper-runtime`  
**Primary branch base / accepted Architecture-94 P2:** `a810122a96b6fc90da25d71eede8da64b7272c98`  
**Architecture-102 adoption checkpoint:** `fab1d776abcdcbf09fb26a257ea7fc86f6201b26`  
**Architecture-103 + validation-plan checkpoint:** `12e41c4e407a79d63ea896773bf8462038ebba27`  
**Accepted PD1A source:** `fa16eef106638e5d6441a05b7f0dd5f757a63e53`  
**Accepted PD1B source:** `1390a16be5f16f7f38757c875a4648f7ef414d70`  
**PD1 certified source:** `e7c2ccbc21972f28b0e82622b426459c67b8007c`  
**PD1 certified tree:** `d14a986f63a600a8b17bef37c56df332c3b3b88c`  
**Historical high-assurance branch:** `feature/p3-r1-recovery-implementation`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded copies are mirrors. Prove the active worktree, branch, HEAD, and clean state before acting.

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

Architecture 102 trusts the owner/Administrator, Windows kernel/boot/SYSTEM, and physical machine control. The bot still protects against practical ordinary-process/configuration/credential/state/duplicate-effect/risk-bypass/recovery failures. It is not designed to survive a malicious local Administrator/SYSTEM/kernel compromise.

The high-assurance Windows line becomes blocking again only if the deployment changes to mutually untrusted local users, commercial distribution, third-party funds, regulatory/custody requirements, or hostile-admin resistance.

## 2. Branch/worktree routing

Primary product branch:

```text
feature/personal-desktop-paper-runtime
base: a810122a96b6fc90da25d71eede8da64b7272c98
```

Dedicated personal-desktop worktree:

```text
F:\AI\worktrees\ai-trading-bot-personal-desktop
feature/personal-desktop-paper-runtime
```

Other preserved worktrees:

```text
historical/high-assurance P3-R1:
  F:\AI\worktrees\ai-trading-bot-p3-r1
  feature/p3-r1-recovery-implementation

paper lineage:
  F:\AI\ai-trading-bot-paper
  feature/reliable-manual-paper-cycle

integration / clean legacy harness:
  F:\AI\ai-trading-bot-integration
  develop

GUI/main worktree:
  F:\AI\ai-trading-bot
```

Preserve unrelated generated/untracked reports and historical pytest/cache evidence. Do not reuse or disturb another active worktree for PD1/PD2 work.

## 3. ChatGPT/Codex workflow

ChatGPT/Sol owns architecture, native Windows security/authority review, exact GitHub diff review, debugging strategy, test/certification gates, merge/deployment/production decisions, and next-step planning.

Model routing:

```text
tiny/simple                                  -> ChatGPT direct
localized/mechanical/frozen contract         -> Luna Extra High
subtle bounded deterministic implementation -> Sol Medium
native Windows/security/authority/recovery   -> Sol High
```

**Tiny scoped status/handoff/docs closeouts are a ChatGPT-direct task by default. Do not delegate them to Codex unless there is a concrete implementation or tooling reason.** This rule already exists in the project workflow; a prior suggestion to send a simple docs closeout to Codex was a workflow regression and should not be repeated.

Do not use subagents unless explicitly requested.

Every bounded Codex task starts with:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
```

Mismatch is a STOP. Do not self-correct with checkout/switch/reset/rebase/clean/worktree operations.

Codex may exact-file stage, commit, and ordinary-push an explicitly authorized checkpoint after focused gates pass. Never `git add .` or `git add -A`. No amend/rebase/merge/force-push/PR-metadata/review-thread changes without explicit approval.

Controlled Windows pytest uses:

```text
--basetemp F:\AI\temp\pytest\<fresh-unique>
-p no:cacheprovider
```

unless cache behavior itself is under test.

## 4. Mandatory personal-desktop security baseline

1. steady-state trading runs under `DESKTOP-I4DOKM7\Trading` / `S-1-5-21-1397534616-3988210162-180023805-1009`, not an administrator;
2. market-data/broker/live credentials stay out of source/plain config and use reviewed Windows-backed storage;
3. paper is default; live later requires explicit arming;
4. every executable order passes deterministic risk authority;
5. strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass risk;
6. durable state outranks process-local assumptions;
7. ambiguous external effects are reconciled/fail-closed, never blindly retried;
8. important runtime/config/state paths are source-governed and use practical least-privilege ACLs;
9. audit/recovery evidence explains attempted effects, durable state, external responses, and retry safety;
10. crash/restart/duplicate/stale/corrupt/conflicting-state testing remains required.

## 5. Frozen C3 production state

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider calls are consumed. Call #5 remains `FAILED / CONFIRMED`. Call #6 remains `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. Provider call #7 is not authorized.

Selected call #6:

```text
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
```

Production identities/paths:

```text
host: DESKTOP-I4DOKM7
creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
runtime: F:\AITradingBot\runtime\python.exe
production temp: F:\AITradingBot\temp
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

No broker order, scheduler, or live effect is authorized here.

## 7. Architecture 103 — PD1 paper-account authority v2

Frozen design:

```text
docs/architecture/103-personal-desktop-paper-account-authority-v2.md
docs/validation/personal-desktop-paper-account-authority-v2-plan.md
```

Architecture 103 reuses Architectures 61/62/63/66/67 and P1/P2 while deliberately removing the parked KSP/LSA/test-user/protected-ceremony dependencies from the primary personal-desktop paper roadmap.

### Fixed paths

```text
final authority root:
  F:\AITradingBot\Paper-v2

provisioning staging root:
  F:\AITradingBot\.Paper-v2.provisioning

Architecture-67 operation root:
  F:\AITradingBot\Paper-v2\runtime

receipt parent:
  F:\AITradingBot\Paper-v2\runtime\paper-operations
```

### Opening-state policy

Production v2 starts as a fresh simulated cash-only account:

```text
starting cash: explicit positive Decimal, no code default
positions: none
realized P&L: 0
open orders: none
application metadata: empty
GENESIS as_of: verified captured_at of accepted selected C3 call #6
```

Starting cash has **not yet been selected**. It belongs to PD1E.

### PD1 accepted/certified implementation

PD1A — **ACCEPTED**:

```text
commit: fa16eef106638e5d6441a05b7f0dd5f757a63e53
```

PD1A implements deterministic account identity, strict canonical anchor/manifest models, exact Architecture-61 GENESIS reuse, explicit positive `Decimal` starting cash, and preserved C1/P2 provenance with no filesystem/provider effect.

PD1B — **ACCEPTED**:

```text
commit: 1390a16be5f16f7f38757c875a4648f7ef414d70
tree:   0e9942f293136e9fd6f3bb5c145ada42800608a6
```

PD1B provides the native Trading token boundary, fixed v2/no-follow path authority, Architecture-103 ACL verification, full A61/A66/A67 lineage reconstruction, graph-derived terminal selection, receipt/dependency replay, and drift rejection. No LSA enumeration is required.

PD1C — **ACCEPTED**:

```text
final accepted source / PD1 certified source:
  e7c2ccbc21972f28b0e82622b426459c67b8007c
certified tree:
  d14a986f63a600a8b17bef37c56df332c3b3b88c
```

PD1C provides a production-disabled publisher and disposable publication harness with create-new staging, exact verification before/after same-parent no-clobber rename, role-policy reuse, crash-state classification, and no automatic cleanup/retry.

The accepted Architecture-103 authority split is:

```text
Trading runtime plane
  genuine process-local ValidatedProductionAuthority + P2
  -> prepares/revalidates exact bundle during readiness

Administrator publication plane
  complete Administrator C1 installation-conformance evidence
  + exact source-owned PD1E publication freeze
  -> publication
```

A Trading runtime capability/P2 permit is never transferred into Administrator. `PersonalDesktopPaperPublicationFreeze` is immutable reviewed data, not a capability.

Current certified source remains deliberately inert:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE = None
```

No real `Paper-v2` publication occurred.

### PD1D source certification — COMPLETE

```text
PD1_SOURCE_ACCEPTED = YES
PD1_SOURCE_CERTIFIED = YES
```

Broad certification evidence at exact commit/tree:

```text
4117 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (417 files already formatted)
git diff --check: PASS
final HEAD: e7c2ccbc21972f28b0e82622b426459c67b8007c
final tree: d14a986f63a600a8b17bef37c56df332c3b3b88c
final worktree status: clean
```

Additional accepted focused evidence:

```text
PD1B initial focused/regression set: 553 passed
PD1B parent correction set: 244 passed
PD1C corrected focused set: 175 passed
PD1A/PD1B/C1 regression set with correction: 513 passed
```

The later standalone source-provenance shell closeout failed only because of PowerShell/Python quoting and protected-path observation behavior. Those harness failures are not repository/test regressions and do not invalidate the completed broad certification.

## 8. Failed v1 publication — preserve untouched

```text
F:\AITradingBot\Paper
  expected FINAL_EXISTS=False

F:\AITradingBot\.Paper.provisioning-v1
  retained historical staging

PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

Ordinary-account observation of the governed namespace may return `AccessDenied`; do not treat that as absence. Never rerun the old publisher. Never delete/repair/rename/migrate/reuse the retained staging tree as incidental cleanup or v2 input.

## 9. High-assurance P3-R1 line — parked, preserved

```text
branch: feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
A101 source: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
A101 tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
```

Architecture 101 remains blocked only for the parked high-assurance profile because Performance Log Users (`S-1-5-32-559`) has `SeBatchLogonRight`.

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

Do not mutate local LSA policy merely to satisfy this parked gate.

## 10. Current roadmap

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

### PD1E scope — NEXT

PD1E is a production-readiness/freeze checkpoint, **not a publication authorization**.

It must:

1. select the explicit starting cash;
2. use the already accepted call-#6/P2 chronology;
3. prepare and freeze exact GENESIS, anchor, and provisioning-manifest bytes plus SHA-256/length;
4. freeze exact `PersonalDesktopPaperPublicationFreeze` values;
5. prove current Administrator C1 installation-conformance readiness;
6. prove fixed-parent and current final/staging occupancy readiness without modifying either;
7. review a tiny future source diff that populates the freeze and, separately, the effect enablement gate;
8. keep publication itself behind a separate explicit user authorization.

No `Paper-v2` creation/mutation occurs merely by completing PD1E readiness.

## 11. Current effect authorization

Still **NOT AUTHORIZED**:

```text
retained v1 staging delete/repair/rename
old publisher rerun
Paper-v2 creation/mutation
.Paper-v2.provisioning creation/mutation
production paper-state mutation
production ACL mutation
account/group/password mutation
LSA policy/right mutation
KSP key/signature/private-export effects
provider call #7
broker order submission
live trading
```

Production/live remains NO-GO.

## 12. Next-session procedure

1. Read Architecture 102, Architecture 103, the PD1 validation plan, this handoff, and `PROJECT_STATUS.md`.
2. Use only `F:\AI\worktrees\ai-trading-bot-personal-desktop` on `feature/personal-desktop-paper-runtime`.
3. Prove worktree/branch/HEAD/clean state and fast-forward this docs-only checkpoint if local is behind remote.
4. Begin **PD1E readiness only**: select explicit starting cash, reproduce the exact call-#6-derived bundle, and freeze its evidence.
5. Keep `PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=False` and production freeze unconfigured until the separately reviewed PD1E source checkpoint.
6. Do not create/mutate `Paper-v2` or `.Paper-v2.provisioning`; do not touch retained v1 staging.
7. ChatGPT/Sol owns the PD1E readiness/freeze review and decides when any tiny freeze/enablement source diff is ready.
8. Any later production publication requires a separate explicit user authorization.
9. Include the next milestone in every verification report.
