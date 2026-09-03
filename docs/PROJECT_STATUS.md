# Project Status and Roadmap

This is the canonical high-level project status for AI Trading Bot. Detailed subsystem contracts remain in `docs/architecture/` and `docs/validation/`; the canonical cross-chat resume document is `docs/AI_TRADING_BOT_HANDOFF.md`.

## Product objective and deployment profile

Build a conservative automated trading platform for a **closed, single-owner personal Windows desktop**, progressing through deterministic research, supervised simulated paper, unattended simulated paper, broker-paper, long paper soak, live-readiness review, tiny restricted live operation, and a polished GUI.

Stable product constraints remain:

```text
US stocks / ETFs
long-only
no margin / leverage / options / shorts / crypto
deterministic risk approval
paper-by-default
complete auditability
```

**Production/live trading remains NO-GO.**

Architecture 102 freezes the personal-desktop threat model. The owner/Administrator, Windows kernel/boot chain, SYSTEM, and physical machine control are trusted. The application must defend against ordinary user-space compromise, accidental execution/configuration, credential leakage, non-admin state tampering, duplicate or ambiguous external effects, risk bypass, accidental live enablement, corrupt/stale durable state, and unattended-operation failures. It is not designed to remain secure after a malicious Administrator/SYSTEM/kernel compromise.

## Primary development line

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
```

Accepted Architecture-94 P1/P2 product checkpoint:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
```

The personal-desktop roadmap forks from that accepted P2 checkpoint so the optional P3-R1 high-assurance Windows ceremony implementation is not carried into the primary product line by default:

```text
branch: feature/personal-desktop-paper-runtime
base:   a810122a96b6fc90da25d71eede8da64b7272c98
Architecture 102 checkpoint: fab1d776abcdcbf09fb26a257ea7fc86f6201b26
```

A dedicated local worktree for this new branch has **not yet been established**. Do not reuse the P3-R1, GUI/main, paper, or integration worktrees for implementation; choose and prove a fresh worktree before PD1 source work.

## Mandatory personal-desktop security baseline

The roadmap pivot reduces ceremony depth, not the controls that materially protect money and credentials. These remain mandatory:

- operational trading runs under the existing dedicated non-admin `Trading` account;
- brokerage and market-data secrets stay out of source/plain configuration and use reviewed Windows-backed secret storage;
- paper is the default and live trading requires a later explicit arming boundary;
- every executable order passes deterministic risk authority;
- strategy, optimizer, GUI, AI, scheduler, and broker/provider adapters cannot bypass risk;
- durable state outranks process-local assumptions;
- ambiguous provider/broker effects are reconciled or fail closed rather than blindly retried;
- important runtime/config/state paths use practical least-privilege ACLs and reject unsafe redirection;
- audit/recovery evidence is sufficient to explain attempts, accepted durable state, external responses, and retry safety;
- crash/restart, duplicate invocation, stale-state, and corruption handling remain required validation work.

The high-assurance Windows track becomes blocking again if the deployment changes to mutually untrusted local users, commercial distribution, third-party funds, regulatory/custody requirements, or defense against a hostile local administrator.

## Frozen C3 / production state

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains permanently `FAILED / CONFIRMED`. Call #6 remains permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. Provider call #7 is not authorized.

Selected call #6:

```text
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
```

Frozen production identities/paths:

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

## Architecture 94 product line

Architecture 94 remains the reliable manually invoked simulated-paper composition. Accepted stages:

```text
P1 pure strategy history / deterministic strategy plan: ACCEPTED
  1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority: ACCEPTED
  a810122a96b6fc90da25d71eede8da64b7272c98
```

The intended product composition remains:

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

The personal-desktop pivot changes how the operational paper-account authority is provisioned; it does not weaken these deterministic trading/state boundaries.

## Retained failed v1 paper-root publication

The earlier v1 production publication attempt remains frozen:

```text
F:\AITradingBot\Paper                       absent
F:\AITradingBot\.Paper.provisioning-v1     retained staging
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

The old publisher must never be rerun. The retained staging tree must not be deleted, repaired, renamed, or repurposed incidentally.

The new personal-desktop line will create a **new versioned paper-account authority** rather than treating the failed v1 state as recovered or using another path as an implicit fallback.

## High-assurance P3-R1 line — preserved, parked, optional

Historical/high-assurance branch:

```text
feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
Architecture-101 source-certified commit: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
Architecture-101 source-certified tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
```

Architectures 95-101 remain valid historical/security work, including retained-staging recovery, signed recovery authorization, KSP machine-key security, the disposable ordinary test principal, protected ceremony evidence root, and split candidate/creator LSA-rights authority.

They are no longer blocking prerequisites for the single-owner personal-desktop paper roadmap.

### Architecture-101 readiness discovery

Fresh Architecture-101 readiness reached:

```text
Gate 1  exact source/tool/disabled-effect identity      PASS
Gate 2  F:\ volume + parent namespace authority         PASS
Gate 3  roots/candidate absence + BUILTIN\Users mapping PASS
Gate 4A local-group topology                            PASS
Gate 4B password/account-policy freeze                  PASS
Gate 5A genuine elevated creator token                  PASS
Gate 5B creator LSA rights baseline                     BLOCKED
```

Gate 5B proved creator-side read capability, then observed `S-1-5-32-559` (Performance Log Users) holding `SeBatchLogonRight`. The frozen Architecture-101 classifier labels that right `UNRESOLVED`, so the high-assurance ceremony correctly remains blocked.

Architecture 102 does **not** relabel that right, weaken Architecture 101, or mutate Windows policy. Instead:

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

Do not run `secedit`, add/remove LSA rights, or change local policy merely to make the parked high-assurance gate pass.

## Revised primary roadmap

### PD0 — personal-desktop profile adoption — CURRENT

Freeze Architecture 102, preserve the high-assurance branch, and move the primary product line to `feature/personal-desktop-paper-runtime` based on accepted P2.

### PD1 — simplified operational paper-account authority v2 — NEXT

Design and implement a new versioned personal-desktop paper authority that:

- reuses accepted GENESIS/checkpoint/lineage and Architecture-67 transition mechanics;
- uses a fixed new versioned root and authority identity;
- leaves retained v1 staging untouched;
- is provisioned by the trusted owner/admin with practical least-privilege ACLs;
- grants `Trading` only the runtime/state access it needs;
- retains create-new/no-clobber publication, exact bytes/identity validation, and fail-closed ambiguous-effect handling;
- does **not** require KSP recovery signing, `P3R1KspTestUser`, exhaustive LSA-rights ceremony, or a separate protected ceremony evidence root;
- remains simulated paper only.

Because PD1 changes Windows runtime/state authority, ChatGPT/Sol High owns its architecture/security review. Implementation is delegated only after the contract is frozen.

### PD2 — reliable supervised manual paper cycle

Complete Architecture-94 composition on the new v2 paper authority. No broker order submission and no unattended scheduling.

### PD3 — repeated supervised paper + crash/recovery validation

Exercise clean restart, crash boundaries, duplicate invocation, stale input, corrupt/conflicting state, and receipt recovery without runtime re-execution.

### PD4 — unattended simulated paper

Add scheduler-owned paper invocation under `Trading`, with duplicate/restart protection and deterministic risk. Required Task Scheduler/batch-logon capability is reviewed as an operational requirement of this phase.

### PD5 — broker-paper integration

Add a broker paper-order API behind the same deterministic risk authority, with separate broker-paper credentials, request/response reconciliation, idempotency, and conservative ambiguous-effect handling.

### PD6 — broker-paper soak and operational hardening

Run sustained unattended paper operation with alerting, reconciliation, backups, credential rotation, restart/failure drills, and measurable reliability gates.

### PD7 — personal-desktop live-readiness

Perform a dedicated money-loss-containment review: separate live credentials, explicit live arming, tiny per-order/per-symbol/daily caps, position/order reconciliation, kill switch, startup/stale-state rejection, idempotency, audit evidence, operator alerts, and appropriate Windows runtime/credential sanity checks.

### PD8 — tiny restricted live, then gradual maturity

Live remains NO-GO until PD7 is separately accepted. Any first live authorization uses intentionally tiny capital and hard limits and expands only after observed stability.

### GUI track

GUI development may continue in parallel as an inspection/control surface. GUI state never becomes credential authority, risk authority, durable trading truth, or implicit live enablement.

## Effect authorization state

Architecture 102 and the roadmap pivot authorize **no operational effects**. Still not authorized:

```text
retained v1 staging delete/repair/rename
old publisher rerun
new paper-root creation
paper-state mutation under a new authority
ACL mutation
account/group/password changes
LSA policy/right changes
KSP key/signature/private-export operations
provider call #7
broker order submission
live trading
```

Production recovery under the old v1 design remains blocked.

## Workflow invariants

- ChatGPT/Sol owns architecture, security/authority review, exact GitHub diff review, test gates, merge/deployment/production decisions, and next milestones.
- ChatGPT may directly perform tiny scoped work/docs closeout.
- Codex may implement bounded work and, when explicitly authorized, exact-file stage, commit, and ordinary-push after focused gates pass.
- Never `git add .` or `git add -A`.
- Worktree/branch/HEAD mismatch is a STOP; do not self-correct it.
- Controlled Windows pytest uses a fresh external `F:\AI\temp\pytest\<unique>` and normally `-p no:cacheprovider`.
- Preserve historical inaccessible caches and unrelated generated/untracked reports.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without explicit approval.

## Documentation workflow

At accepted milestones update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

`docs/AI_DEVELOPMENT_WORKFLOW.md` changes only when a reusable development workflow rule changes. This personal-desktop pivot is a product/security-roadmap decision, so no workflow-doc change is required.
