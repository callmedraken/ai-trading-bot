# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**Primary product branch:** `feature/personal-desktop-paper-runtime`  
**Primary branch base / accepted Architecture-94 P2:** `a810122a96b6fc90da25d71eede8da64b7272c98`  
**Architecture-102 adoption checkpoint:** `fab1d776abcdcbf09fb26a257ea7fc86f6201b26`  
**Architecture-103 + validation-plan checkpoint:** `12e41c4e407a79d63ea896773bf8462038ebba27`  
**Accepted PD1A source checkpoint:** `fa16eef106638e5d6441a05b7f0dd5f757a63e53`  
**Accepted PD1B source checkpoint:** `1390a16be5f16f7f38757c875a4648f7ef414d70`  
**Accepted PD1B source tree:** `0e9942f293136e9fd6f3bb5c145ada42800608a6`  
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

Existing parallel worktrees:

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

Preserve unrelated generated/untracked reports and historical pytest/cache evidence. Do not reuse or disturb another active worktree for PD1.

## 3. ChatGPT/Codex workflow

ChatGPT/Sol owns architecture, native Windows security/authority review, exact GitHub diff review, debugging strategy, test/certification gates, merge/deployment/production decisions, and next-step planning.

Model routing:

```text
tiny/simple                                  -> ChatGPT direct
localized/mechanical/frozen contract         -> Luna Extra High
subtle bounded deterministic implementation -> Sol Medium
native Windows/security/authority/recovery   -> Sol High
```

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

Keep these as product requirements:

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
checkpoint: 12e41c4e407a79d63ea896773bf8462038ebba27
```

Architecture 103 reuses Architectures 61/62/63/66/67 and P1/P2. It deliberately removes the parked KSP/LSA/test-user/protected-ceremony dependencies from the primary personal-desktop paper roadmap.

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

Initial layout:

```text
Paper-v2\
  personal-desktop-paper-account-authority.json
  paper-account-genesis-<genesis-checkpoint-id>\
    paper-account-checkpoint-<genesis-checkpoint-id>.json
  runtime\
    paper-operations\
```

### Schemas and identity

```text
anchor schema: personal-desktop-paper-account-authority/v1
layout:        personal-desktop-paper-layout/v1
manifest:      personal-desktop-paper-account-provisioning/v1
UUID5 ns:      022bbd87-6bea-5fd0-a323-5fa355616643
```

Paper-account identity binds the validated machine-authority ID, exact approved Trading SID, and exact GENESIS checkpoint ID/hash/length. Paths, environment, wall clock, random UUIDs, and C3 transport paths do not create account identity.

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

Starting cash has **not yet been selected**. It belongs to the later production-bundle/readiness freeze.

### Provisioning contract

One trusted elevated owner/admin operation:

```text
validated C1 machine + Trading binding
-> fixed safe F:\AITradingBot parent
-> exact reviewed offline manifest/anchor/GENESIS bytes
-> final + staging absence
-> fixed staging creation
-> exact layout + create-new writes + flush
-> final ACL application
-> full staged bytes/layout/ACL verification
-> same-parent no-clobber staging-to-final rename
-> full final reopen/reverification
```

The rename is the publication commit point.

Staging need not receive final ACLs at the instant each child is created because it exists below the trusted administrator-controlled parent, is not authority before publication, and must receive/verify final ACLs before rename.

### Runtime security

Steady-state authority requires exact approved Trading SID, primary non-elevated token, no thread impersonation, and no enabled Administrators membership. No LSA-right enumeration is required.

Immutable root/anchor/GENESIS are administrator-owned and Trading-read-only. `runtime` / `paper-operations` grant only the approved Trading SID the data rights needed by Architecture 67. Unrelated principals are rejected.

For the fixed ancestor chain, the volume role allows ordinary concrete data/sibling rights that do not permit replacement of the governed child, while rejecting `FILE_DELETE_CHILD`, `WRITE_DAC`, `WRITE_OWNER`, and unknown masks. The immediate `F:\AITradingBot` parent remains more restrictive and rejects unrelated delete/replacement/security-control authority.

### Accepted source implementation

PD1A — **ACCEPTED**:

```text
commit: fa16eef106638e5d6441a05b7f0dd5f757a63e53
```

Implements the pure deterministic v2 account-ID, strict anchor/manifest models, exact Architecture-61 GENESIS reuse, explicit positive `Decimal` starting cash, and preserved C1/P2 provenance. No filesystem/provider effect occurs.

PD1B — **ACCEPTED**:

```text
commit: 1390a16be5f16f7f38757c875a4648f7ef414d70
tree:   0e9942f293136e9fd6f3bb5c145ada42800608a6
```

The accepted PD1B tree includes the initial read-authority checkpoint `59703c0fec6038b223876ad89d632dbab1e915cb` plus bounded parent-policy correction `1390a16be5f16f7f38757c875a4648f7ef414d70`.

PD1B provides:

- bounded native process-token proof for exact Trading SID, primary token, non-elevated state, no thread impersonation, and no enabled Administrators authority;
- no LSA-right enumeration dependency;
- exact source-owned v2 paths and bounded no-follow/pinned object reads;
- role-based ACL verification independent of the existing C1 policy;
- finite anchor/artifact/inventory/pinned-object bounds;
- full installed account reconstruction through Architecture 61/66/67;
- graph-derived unique terminal selection rather than filename/time/newest heuristics;
- receipt replay and exact historical snapshot/configuration dependency checks;
- final token, identity, ACL, content, and inventory drift rejection.

Focused evidence reported during implementation:

```text
initial PD1B focused + directly affected regressions: 553 passed
parent-security correction verification:             244 passed
Ruff check / Ruff format check:                       passed
Git whitespace/diff checks:                           passed
```

Real installed-v2 end-to-end Windows validation remains unperformed because production `Paper-v2` does not yet exist and production effects remain disabled.

### Crash/recovery rule

No automatic provisioning retry. If staging creation may have begun and the publisher exits unexpectedly, that effect authorization is consumed. Reconcile final/staging read-only before any later action. Never silently delete, repair, or retry crash-left staging.

### Source effect gate

Throughout PD1 implementation and source certification:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=false
```

A later separately reviewed checkpoint freezes exact bundle bytes/hashes, starting cash, readiness evidence, and an enablement diff before any production effect discussion.

## 8. Failed v1 publication — preserve untouched

```text
F:\AITradingBot\Paper
  FINAL_EXISTS=False

F:\AITradingBot\.Paper.provisioning-v1
  STAGING_EXISTS=True

PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

Never rerun the old publisher. Never delete/repair/rename/migrate/reuse the retained staging tree as incidental cleanup or v2 input.

## 9. High-assurance P3-R1 line — parked, preserved

```text
branch: feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
A101 source: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
A101 tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
```

A101 readiness reached Gate 5A and remains blocked at 5B because Performance Log Users (`S-1-5-32-559`) has `SeBatchLogonRight`, which the frozen A101 classifier labels `UNRESOLVED`.

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

Do not mutate local LSA policy just to satisfy this parked high-assurance gate.

## 10. Current roadmap

```text
PD0  personal-desktop profile adoption                     COMPLETE
PD1  personal-desktop paper-account authority v2           CURRENT
  PD1A pure anchor/account-ID/provisioning bundle           ACCEPTED
  PD1B Windows read-only authority + token/ACL/path         ACCEPTED
  PD1C disabled publisher + disposable publication tests   NEXT
  PD1D source diff review + broad certification
  PD1E separate production bundle/readiness/effect gate
PD2  reliable supervised manual paper cycle
PD3  supervised crash/recovery validation
PD4  unattended simulated paper under Trading
PD5  broker-paper integration
PD6  broker-paper soak / operational hardening
PD7  personal-desktop live-readiness
PD8  tiny restricted live -> gradual maturity
```

Implementation routing for PD1:

```text
PD1A frozen mechanical model                 -> Luna Extra High
PD1A subtle P2/A61 integration               -> Sol Medium
PD1B/PD1C native Windows authority/security  -> Sol High
```

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

Accepted PD1A/PD1B source grants no production effect authority.

## 12. Next-session procedure

1. Read Architecture 102, Architecture 103, the PD1 validation plan, this handoff, and `PROJECT_STATUS.md`.
2. Use only `F:\AI\worktrees\ai-trading-bot-personal-desktop` on `feature/personal-desktop-paper-runtime`.
3. Prove worktree/branch/HEAD/clean state; fast-forward any docs-only remote checkpoints before starting a Codex task.
4. Implement **PD1C only** with Sol High: production-disabled publisher plus disposable publication/crash-state tests.
5. Keep `PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=false`; no real `Paper-v2`, staging, ACL, account, provider, broker, or live effect is authorized.
6. Run focused PD1C tests plus directly affected PD1A/PD1B regressions, Ruff, format check, and `git diff --check`.
7. Codex may exact-file stage/commit/ordinary-push the scoped PD1C checkpoint when the prompt explicitly authorizes it.
8. ChatGPT/Sol reviews the authoritative GitHub diff before PD1D broad source certification.
9. Include the next milestone in every verification report.
