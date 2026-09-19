# Architecture 102: Personal-desktop security profile and roadmap pivot

## Status and scope

**DOCS-ONLY PRODUCT-SECURITY / ROADMAP CHECKPOINT -- NO EFFECT AUTHORIZATION**

This checkpoint narrows the deployment threat model for AI Trading Bot to its actual intended environment: a closed, single-owner trading application running on the owner's personal Windows desktop.

It changes which security work is required before the product roadmap may continue. It does **not** change any certified source behavior, does not weaken the frozen Architecture-101 classifier, does not repair or reinterpret the retained failed production paper-root publication, and does not authorize any filesystem, account, password, group, LSA, KSP, provider, brokerage, or live-trading effect.

Architectures 95 through 101 remain valid high-assurance security work and historical evidence. They are reclassified as an optional hardening track rather than a blocking prerequisite for the personal-desktop paper-trading roadmap.

## Deployment threat model

### Trusted boundary

For the personal-desktop profile, the following are trusted and outside the application's protection boundary:

- the machine owner / administrator;
- Windows kernel, boot chain, and SYSTEM authority;
- physical control of the machine;
- deliberate administrator changes made by the owner.

The application is not attempting to remain secure after a malicious Administrator/SYSTEM/kernel compromise. That is not a realistic protection boundary for a local Python trading bot on an owner-controlled desktop.

### In-scope threats

The product must still defend against the risks that are realistic and material for this deployment:

- compromised Python packages or ordinary user-space processes;
- accidental execution from the wrong account or runtime;
- plaintext or casually accessible brokerage/data credentials;
- non-admin local tampering with production configuration or durable trading state;
- duplicate/replayed/ambiguous provider or brokerage effects after crashes;
- strategy, GUI, AI, scheduler, or operator paths bypassing deterministic risk;
- accidental transition from paper to live trading;
- corrupted, stale, internally inconsistent, or ambiguous durable state;
- unattended-operation failures that could create duplicate or uncontrolled orders.

### Revisit trigger

The high-assurance Windows track becomes blocking again if the deployment model changes materially, including any of:

- multiple mutually untrusted local users;
- commercial distribution to machines not controlled by the owner;
- management of third-party funds;
- regulatory / custody / forensic assurance requirements;
- a requirement to defend against a hostile local administrator.

## Mandatory personal-desktop security baseline

The following controls remain product requirements and are not downgraded by this profile.

### Dedicated ordinary trading identity

Operational trading processes should run as the existing dedicated ordinary account:

```text
DESKTOP-I4DOKM7\Trading
S-1-5-21-1397534616-3988210162-180023805-1009
```

The account remains non-administrator. Administrative setup may be performed by the owner, but the steady-state bot should not require elevation.

### Credential isolation

Brokerage and market-data secrets must remain outside source code and ordinary configuration files and use reviewed Windows-backed secret storage. Paper and future live credentials must be distinguishable and must never be selected merely from ambient environment variables or a caller-provided path.

### Paper-by-default / explicit live arming

Paper remains the default execution mode. Live trading requires a later separate readiness decision and an explicit operator arming boundary. A GUI state, strategy decision, scheduler launch, configuration typo, or presence of credentials must never silently enable live order submission.

### Deterministic risk remains authoritative

Every order capable of reaching paper-broker or live-broker submission must pass the deterministic risk authority. Strategy, optimizer, GUI, AI, scheduler, and broker adapters remain proposal/transport layers and may not bypass risk decisions.

### Durable ambiguity handling

The existing design principle remains: durable state outranks process-local assumptions. Provider and brokerage effects must be idempotent/reconciled where possible, and ambiguous external effects must not be automatically retried as though they definitely failed.

### Controlled runtime and state

Operational runtime/config/state paths must be fixed or otherwise source-governed, must reject unsafe redirection, and must not grant ordinary unrelated users/processes authority to rewrite state that the bot later treats as trusted.

The personal-desktop profile does not require every object to participate in a formal ceremony; it does require practical least-privilege ACLs and fail-closed identity checks at the important execution/state boundaries.

### Audit and recovery

Paper and future broker operations must retain enough deterministic evidence to explain what was attempted, what durable state was accepted, what broker response was observed, and whether retry/recovery is safe. Crash/restart testing remains a product milestone.

## High-assurance Windows track: preserved but no longer blocking

The following work remains valid defense-in-depth, but is no longer required before the personal-desktop paper roadmap proceeds:

- P3-R1 recovery-signing trust re-establishment;
- Windows Software KSP machine-key denial experiments;
- creation of `P3R1KspTestUser` solely to prove ordinary-principal KSP denial;
- the protected ceremony evidence-root protocol;
- exact candidate/creator split-authority console transfer;
- exhaustive per-SID LSA account-right classification;
- signed recovery authorization intended to survive stronger local adversaries.

No source should be changed merely to make those high-assurance gates green for the personal-desktop profile. If that track is resumed later, it resumes under its existing strict contracts.

## Architecture-101 readiness finding

The restarted Architecture-101 readiness sequence established Gates 1 through 5A and then discovered at Gate 5B that `S-1-5-32-559` (Performance Log Users) has:

```text
SeBatchLogonRight
```

The frozen Architecture-101 classifier correctly labels that right `UNRESOLVED`, so the Architecture-101 ceremony remains blocked.

This checkpoint does not relabel the right, add it to the classifier, remove it from Windows policy, or treat the Architecture-101 gate as passed. Instead:

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

The machine's LSA policy must not be mutated merely to satisfy the historical high-assurance gate.

## Retained failed production paper-root state

The earlier production publication failure remains frozen:

```text
F:\AITradingBot\Paper                  absent
F:\AITradingBot\.Paper.provisioning-v1 retained staging
```

The old publisher must not be rerun, and the retained staging tree must not be deleted or repaired as an incidental consequence of this roadmap pivot.

The personal-desktop line will design a **new versioned operational paper-account authority** rather than silently treating the old retained staging state as recovered or using an alternate path as a fallback to the failed v1 authority.

## Revised primary roadmap

### PD0 -- personal-desktop profile adoption

Current checkpoint. Freeze this threat model, park the high-assurance P3-R1 line, and resume product work from the accepted Architecture-94 P2 source checkpoint:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
```

The P3-R1 branch remains preserved as historical/high-assurance work.

### PD1 -- simplified operational paper-account authority v2

Design and implement a new versioned personal-desktop paper-account root/authority that:

- reuses the accepted deterministic GENESIS/checkpoint/lineage and Architecture-67 transition mechanics;
- uses a fixed new versioned root and a new authority identity rather than falling back to the failed v1 root;
- leaves the retained v1 staging tree untouched;
- is provisioned by the trusted owner/admin with practical least-privilege ACLs;
- grants the `Trading` account only the runtime access it needs;
- does not require KSP recovery signing, a disposable test principal, LSA-rights ceremonies, or a separate protected ceremony evidence root;
- retains create-new/no-clobber publication, exact bytes/identity validation, and fail-closed ambiguity handling;
- remains simulated paper only.

Because PD1 changes Windows runtime/state authority, ChatGPT/Sol High owns its architecture and security review. Bounded implementation may be delegated only after the contract is frozen.

### PD2 -- reliable supervised manual paper cycle

Complete Architecture-94 composition on the new v2 paper authority:

```text
selected verified C3 snapshot
+ explicit deterministic strategy history
+ authoritative paper-account tip
-> strategy plan
-> planner/proposal
-> deterministic risk
-> simulated paper execution
-> successor checkpoint / lineage verification
-> durable operation receipt
```

No broker order submission and no unattended scheduling yet.

### PD3 -- repeated supervised paper / crash-recovery validation

Run multiple manually initiated cycles and deliberately test:

- clean restart;
- crash before/after durable transition boundaries;
- duplicate invocation;
- stale snapshot/history rejection;
- corrupted or conflicting paper state;
- receipt recovery without runtime re-execution.

The goal is operational reliability, not additional Windows ceremony depth.

### PD4 -- unattended simulated paper

Add a scheduler-owned paper invocation under the dedicated `Trading` account. The scheduler must remain paper-only, respect deterministic risk, and have explicit duplicate/restart protection. Task Scheduler / batch-logon requirements are reviewed as operational requirements of this phase rather than treated as inherently suspicious privileges.

### PD5 -- broker-paper integration

Introduce a real broker's paper-trading order API behind the same deterministic risk authority. Separate broker-paper credentials from market-data credentials, add request/response reconciliation and idempotency, and prove that ambiguous broker effects cannot produce blind duplicate orders.

### PD6 -- broker-paper soak and operational hardening

Run sustained unattended paper operation with alerting, reconciliation, backups, credential rotation, restart/failure drills, and measurable reliability gates.

### PD7 -- personal-desktop live-readiness

Only after a successful paper soak, perform a dedicated live-readiness review focused on money-loss containment:

- separate live credentials;
- explicit live arming;
- tiny per-order / per-symbol / daily notional caps;
- deterministic risk and position reconciliation;
- kill switch / emergency disable;
- startup and stale-state rejection;
- broker-order idempotency/reconciliation;
- audit logging and operator alerts;
- Windows account/runtime/credential sanity checks appropriate to the personal-desktop threat model.

The high-assurance Architectures 95-101 may be reconsidered here if the deployment threat model has expanded, but they are not automatically required.

### PD8 -- tiny restricted live, then gradual maturity

Live remains NO-GO until PD7 is separately accepted. Initial live operation, if ever authorized, starts with intentionally tiny capital and hard limits, then expands only after observed stability.

### GUI track

GUI development may continue in parallel as an inspection/control surface, but it never becomes the source of credentials, risk authority, durable trading truth, or implicit live enablement.

## Branching consequence

The primary personal-desktop development line should fork from accepted P2 rather than carry the P3-R1 high-assurance implementation forward by default:

```text
base:   a810122a96b6fc90da25d71eede8da64b7272c98
branch: feature/personal-desktop-paper-runtime
```

This keeps accepted P1/P2 functionality while leaving the P3-R1 KSP/recovery/ceremony source isolated on its existing branch for possible future resumption.

## Effect authorization state

This docs checkpoint authorizes **no effects**. In particular it does not authorize:

```text
retained staging deletion/repair
old publisher rerun
new paper-root creation
ACL mutation
account/group/password changes
LSA policy/right changes
KSP key operations
provider call #7
broker order submission
live trading
```

The next checkpoint is architecture/design for PD1, not execution.