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

Personal-desktop docs checkpoints:

```text
Architecture 102 adoption: fab1d776abcdcbf09fb26a257ea7fc86f6201b26
Architecture 103 + validation plan: 12e41c4e407a79d63ea896773bf8462038ebba27
```

A dedicated local worktree for this branch has **not yet been established**. Do not reuse the P3-R1, GUI/main, paper, or integration worktrees for PD1 source implementation.

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

The product composition to preserve is:

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

## Architecture 103 — personal-desktop paper-account authority v2 — FROZEN

Architecture 103 is the PD1 design for a practical new simulated-paper account authority. It reuses Architectures 61/62/63/66/67 and Architecture-94 P1/P2 while removing the parked KSP/LSA/test-principal/ceremony dependencies from the primary roadmap.

Design and validation plan:

```text
docs/architecture/103-personal-desktop-paper-account-authority-v2.md
docs/validation/personal-desktop-paper-account-authority-v2-plan.md
checkpoint: 12e41c4e407a79d63ea896773bf8462038ebba27
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

### v2 identity

Anchor schema:

```text
personal-desktop-paper-account-authority/v1
```

Layout:

```text
personal-desktop-paper-layout/v1
```

Provisioning manifest:

```text
personal-desktop-paper-account-provisioning/v1
```

Deterministic paper-account UUID5 namespace:

```text
022bbd87-6bea-5fd0-a323-5fa355616643
```

Identity binds exact machine-authority ID, approved Trading SID, and exact GENESIS checkpoint ID/hash/length. Paths, wall clock, environment, random UUIDs, and C3 selection paths do not create account identity.

### Opening account policy

The first v2 account is fresh simulated cash-only state:

```text
explicit positive starting cash; no code default
positions: none
realized P&L: 0
open orders: none
application metadata: empty
GENESIS as_of: exact verified captured_at of accepted selected C3 call #6
```

Exact starting cash is deliberately **not selected yet**; it becomes part of a later production-bundle/readiness freeze, not source architecture.

### Provisioning and runtime security

Provisioning is a one-time trusted-owner/admin operation with a validated C1 machine/Trading binding, fixed safe parent, exact offline bundle, absent final/staging paths, staged exact bytes, final ACL application/verification, and same-parent no-clobber rename. Rename is the publication commit point.

Steady-state runtime authority requires the exact approved Trading SID, primary non-elevated token, no thread impersonation, and no enabled Administrators membership. No LSA-right enumeration, KSP test key, disposable principal, recovery signature, or protected ceremony-evidence root is required.

Immutable root/anchor/GENESIS remain administrator-owned and Trading-read-only. Runtime containers grant the approved Trading SID only the data rights required for Architecture-67 transitions/receipts. Unrelated principals are rejected.

### Crash semantics

No automatic provisioning retry exists. If v2 staging creation may have begun and the process exits unexpectedly, that effect authorization is consumed and read-only reconciliation is required. Crash-left staging is never silently deleted/repaired/retried.

### Production source gate

Through PD1 implementation and source certification:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=false
```

Production root mutation remains blocked until a separate source-certified readiness/bundle freeze and explicit user authorization.

## Retained failed v1 publication

Historical state remains frozen:

```text
F:\AITradingBot\Paper                       absent
F:\AITradingBot\.Paper.provisioning-v1     retained staging
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

The old publisher must never be rerun. The retained staging tree must not be deleted, repaired, renamed, migrated, or used as v2 input/fallback.

## High-assurance P3-R1 line — preserved, parked, optional

Historical branch:

```text
feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
Architecture-101 source-certified commit: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
Architecture-101 source-certified tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
```

Fresh Architecture-101 readiness reached Gate 5A and remains blocked at Gate 5B because Performance Log Users (`S-1-5-32-559`) holds `SeBatchLogonRight`, which the frozen classifier correctly labels `UNRESOLVED`.

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

Do not change host LSA policy merely to make the parked gate pass.

## Revised primary roadmap

### PD0 — personal-desktop profile adoption — COMPLETE

Architecture 102 adopted; new branch created from accepted P2; high-assurance branch preserved.

### PD1 — personal-desktop paper-account authority v2 — CURRENT

Architecture 103 and validation plan are frozen. Implementation sequence:

```text
PD1A pure anchor / account-ID / provisioning-bundle model      NEXT
PD1B Windows read-only authority + token/ACL/path policy
PD1C production-disabled publisher + disposable publication tests
PD1D exact diff review + broad source certification
PD1E separate production bundle/readiness/effect authorization
```

Model routing:

```text
PD1A mechanical frozen-contract implementation -> Luna Extra High
PD1A if P2/A61 integration proves subtle        -> Sol Medium
PD1B/PD1C native Windows authority/security     -> Sol High
```

### PD2 — reliable supervised manual paper cycle

Compose Architecture-94 against the verified v2 authority and account-scoped mutex. No broker submission or scheduler.

### PD3 — repeated supervised paper + crash/recovery validation

Exercise restart, duplicate invocation, stale/corrupt/conflicting state, publication interruptions, and zero-runtime-call receipt recovery.

### PD4 — unattended simulated paper

Add scheduler-owned paper invocation under Trading with deterministic risk and duplicate/restart protection. Task Scheduler/batch-logon capability is reviewed as an operational requirement, not automatically as a hostile privilege.

### PD5 — broker-paper integration

Add broker-paper order submission behind deterministic risk with separate credentials, idempotency, response reconciliation, and conservative ambiguous-effect handling.

### PD6 — broker-paper soak and operational hardening

Sustained unattended broker-paper use with alerting, reconciliation, backups, credential rotation, restart/failure drills, and measurable reliability gates.

### PD7 — personal-desktop live-readiness

Separate live credentials, explicit live arming, tiny hard limits, reconciliation, kill switch, startup/stale-state rejection, idempotency, audit evidence, and operator alerts.

### PD8 — tiny restricted live, then gradual maturity

Live remains NO-GO until PD7 is separately accepted.

## Effect authorization state

Architecture 103 is docs-only and authorizes **no operational effects**. Still not authorized:

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
- ChatGPT may directly perform tiny scoped work/docs closeout.
- Codex may implement bounded work and, when explicitly authorized, exact-file stage/commit/ordinary-push after focused gates pass.
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

Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only for a new reusable workflow rule. Architecture 103 changes product/security architecture, not the reusable development workflow.
