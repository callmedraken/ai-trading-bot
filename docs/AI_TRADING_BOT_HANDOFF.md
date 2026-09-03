# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**Primary personal-desktop branch:** `feature/personal-desktop-paper-runtime`  
**Primary branch base / accepted Architecture-94 P2:** `a810122a96b6fc90da25d71eede8da64b7272c98`  
**Architecture-102 docs checkpoint:** `fab1d776abcdcbf09fb26a257ea7fc86f6201b26`  
**Historical high-assurance branch:** `feature/p3-r1-recovery-implementation`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded copies are mirrors only. Prove the active worktree, branch, HEAD, and clean state before acting.

## 1. Product goal and actual deployment model

Build a conservative automated trading platform for a **closed, single-owner personal Windows desktop**, progressing through:

**deterministic research → supervised simulated paper → unattended simulated paper → broker-paper → long paper soak → personal-desktop live-readiness → tiny restricted live → mature automated operation → polished GUI.**

Stable product constraints:

```text
US stocks / ETFs
long-only
no margin / leverage / options / shorts / crypto
deterministic risk approval
paper-by-default
complete auditability
```

Architecture 102 narrows the security threat model to the real deployment. The machine owner/Administrator, Windows kernel/boot chain, SYSTEM, and physical control are trusted. The bot must defend against ordinary user-space compromise, accidental execution/configuration, credential leakage, non-admin state tampering, duplicate or ambiguous external effects, risk bypass, accidental live enablement, stale/corrupt durable state, and unattended-operation failures.

The application is **not** attempting to remain secure after a malicious local Administrator/SYSTEM/kernel compromise.

Reconsider the optional high-assurance Windows track if the deployment later includes mutually untrusted local users, commercial distribution, third-party funds, regulatory/custody requirements, or a hostile-admin threat model.

## 2. Branch/worktree routing

Primary product branch:

```text
feature/personal-desktop-paper-runtime
base: a810122a96b6fc90da25d71eede8da64b7272c98
```

This branch intentionally forks from accepted Architecture-94 P2 instead of inheriting the P3-R1 KSP/recovery/ceremony implementation.

A dedicated local worktree for the new branch has **not yet been created**. Before PD1 implementation, choose a fresh path and create/prove it explicitly. Do not reuse another active worktree.

Existing worktrees remain:

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

Preserve unrelated generated/untracked reports and historical pytest/cache evidence.

## 3. ChatGPT/Codex workflow

ChatGPT/Sol owns architecture, Windows security/authority review, exact GitHub diff review, debugging strategy, test/certification gates, merge/deployment/production decisions, and next-step planning. ChatGPT may directly perform tiny scoped work and docs closeout.

Model routing remains:

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
```

Any worktree/branch/HEAD mismatch is a STOP. Codex must not self-correct with checkout/switch/reset/rebase/clean/worktree operations.

After focused gates pass, Codex may exact-file stage, commit, and ordinary-push the approved feature branch when explicitly authorized. Never `git add .` or `git add -A`. No amend/rebase/merge/force-push/PR metadata/review-thread changes or unrelated cleanup without explicit approval.

Controlled Windows pytest uses:

```text
--basetemp F:\AI\temp\pytest\<fresh-unique>
-p no:cacheprovider
```

unless a test specifically requires cache behavior. Preserve inaccessible historical `.pytest_cache` state.

## 4. Mandatory personal-desktop security baseline

The roadmap pivot removes disproportionate ceremony, not material safety controls.

Keep all of these as product requirements:

1. **Dedicated ordinary trading identity.** Operational trading runs under `DESKTOP-I4DOKM7\Trading` / SID `S-1-5-21-1397534616-3988210162-180023805-1009`, not an administrator account.
2. **Credential isolation.** Market-data, broker-paper, and future live credentials stay out of source/plain config and use reviewed Windows-backed storage. Credential classes/versions remain explicit.
3. **Paper default / explicit live arming.** Credentials, GUI state, scheduler launch, or configuration alone can never silently switch to live.
4. **Deterministic risk authority.** Every order capable of reaching a paper broker or live broker passes deterministic risk. Strategy/optimizer/GUI/AI/scheduler/adapters cannot bypass it.
5. **Durable ambiguity handling.** Durable state outranks process-local assumptions. Ambiguous provider/broker effects are reconciled or fail closed; never blindly retry.
6. **Controlled runtime/state.** Important runtime/config/state locations use source-governed identity and practical least-privilege ACLs. Unrelated ordinary processes must not be able to rewrite state later treated as authoritative.
7. **Audit/recovery.** Retain deterministic evidence sufficient to explain attempted effects, durable commitments, broker/provider responses, and whether recovery/retry is safe.
8. **Operational failure testing.** Crash/restart, duplicate invocation, stale inputs, corruption/conflicts, and receipt recovery are roadmap gates.

## 5. Frozen C3 production state

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider calls are consumed. Call #5 remains permanently `FAILED / CONFIRMED`. Call #6 remains permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED`; never rerun it. Provider call #7 is not authorized.

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

Architecture 94 remains the reliable manually invoked simulated-paper composition.

Accepted stages:

```text
P1 pure strategy history / deterministic strategy plan
  1028e60b99c27cef0994f40d6ce381392abfb0f8

P2 read-only selected-C3 snapshot authority
  a810122a96b6fc90da25d71eede8da64b7272c98
```

The composition to preserve is:

```text
selected verified C3 snapshot
+ explicit deterministic strategy history
+ authoritative paper-account tip
-> pure deterministic strategy plan
-> existing planner / proposal path
-> deterministic portfolio risk
-> simulated paper execution
-> successor checkpoint + full-lineage verification
-> Architecture-67 durable transition + receipt
```

No broker order submission, unattended scheduling, or live trading is authorized by Architecture 94.

## 7. Failed v1 paper-root publication remains frozen

The earlier production publication attempt remains retained:

```text
F:\AITradingBot\Paper
  FINAL_EXISTS=False

F:\AITradingBot\.Paper.provisioning-v1
  STAGING_EXISTS=True

PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

Do not rerun the old publisher. Do not delete, repair, rename, or reuse the retained staging tree as an incidental cleanup step.

Architecture 102 chooses a **new versioned personal-desktop paper-account authority** instead of declaring this v1 failure recovered or using another path as a fallback.

## 8. High-assurance P3-R1 line — preserved but parked

Historical branch:

```text
feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
```

Architectures 95-101 remain valid historical/high-assurance work. Architecture-101 source certification remains accepted:

```text
source commit: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
source tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
focused:       63 passed + strengthened SID regression
broad current slice: 3494 passed, 24 skipped
legacy clean harness: 758 passed
```

That line includes retained-staging recovery, signed recovery authorization, Windows Software KSP machine-key proof, `P3R1KspTestUser`, a protected ceremony evidence root, and split candidate/creator LSA-rights collection.

These are **optional defense-in-depth** under the personal-desktop profile and no longer block simulated-paper product development.

### Architecture-101 readiness discovery

Fresh A101 readiness established:

```text
Gate 1  source/tool + disabled-effect identity           PASS
Gate 2  F:\ fixed NTFS + parent namespace authority      PASS
Gate 3  roots/candidate absence + BUILTIN\Users mapping  PASS
Gate 4A local-group topology                             PASS
Gate 4B account/password policy                          PASS
Gate 5A fully elevated creator token                     PASS
Gate 5B creator-side LSA rights baseline                 BLOCKED
```

Gate 5B proved the elevated creator can read LSA account rights. It then observed Performance Log Users (`S-1-5-32-559`) holding:

```text
SeBatchLogonRight
```

Architecture 101's frozen classifier labels that right `UNRESOLVED`, so its high-assurance ceremony remains blocked. The later shell text that printed a PASS after the throw is not evidence.

Architecture 102 does not alter that classifier and does not mutate Windows policy:

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

Do not use `secedit`, add/remove LSA rights, or otherwise change host policy merely to satisfy the parked gate.

## 9. Architecture 102 — personal-desktop security profile

Architecture 102 is the roadmap/security pivot checkpoint:

```text
commit: fab1d776abcdcbf09fb26a257ea7fc86f6201b26
branch: feature/personal-desktop-paper-runtime
```

Key decision:

- keep the practical Windows security controls that isolate ordinary bot execution, credentials, runtime/state, and trading authority;
- stop treating exhaustive Windows ceremony/LSA/KSP proofs as prerequisites for a single-owner personal desktop;
- preserve those proofs on the historical branch for future stronger threat models;
- spend the next engineering budget on reliable paper operation, crash recovery, broker-paper reconciliation, risk controls, and live-loss containment.

Architecture 102 is docs-only and authorizes no effect.

## 10. Revised primary roadmap

### PD0 — personal-desktop profile adoption — CURRENT

Architecture 102 and the canonical roadmap/handoff update. Preserve P3-R1 history; make the new branch the primary product line.

### PD1 — simplified operational paper-account authority v2 — NEXT

Freeze a new source-governed personal-desktop paper authority that:

```text
reuses deterministic GENESIS/checkpoint/lineage + Architecture-67
uses a new fixed versioned root and authority identity
leaves v1 retained staging untouched
is provisioned by trusted owner/admin
uses practical least-privilege ACLs
grants Trading only required runtime/state access
retains create-new/no-clobber publication
retains exact byte/identity validation
retains fail-closed ambiguity semantics
does not require KSP recovery signing / test principal / LSA ceremony / protected ceremony root
remains simulated paper only
```

PD1 is a Windows state/authority design, so ChatGPT/Sol High owns architecture/security review. Do not implement or create the root until the contract is frozen and a separate implementation/effect checkpoint is authorized.

### PD2 — reliable supervised manual paper cycle

Complete Architecture-94 composition against the new v2 authority. No broker submission or scheduler yet.

### PD3 — repeated supervised paper + crash/recovery validation

Test clean restart, crash boundaries, duplicate invocation, stale market/history input, corrupt/conflicting paper state, and zero-runtime-call receipt recovery.

### PD4 — unattended simulated paper

Add scheduler-owned paper execution under `Trading`, with explicit duplicate/restart protection and deterministic risk. Task Scheduler / batch-logon capability is treated as an operational requirement to review, not automatically as a hostile privilege.

### PD5 — broker-paper integration

Add real broker-paper order submission behind deterministic risk. Use separate broker-paper credentials, request/response reconciliation, idempotency, and conservative handling of uncertain broker effects.

### PD6 — broker-paper soak / operational hardening

Sustained unattended paper use with alerting, reconciliation, backups, credential rotation, restart/failure drills, and measurable reliability gates.

### PD7 — personal-desktop live-readiness

Only after successful paper soak, review:

```text
separate live credentials
explicit live arming
tiny per-order / symbol / daily caps
deterministic risk
position + open-order reconciliation
kill switch / emergency disable
startup + stale-state rejection
broker idempotency / ambiguity reconciliation
complete audit logging
operator alerts
appropriate Windows account/runtime/credential sanity checks
```

Reconsider the high-assurance 95-101 line here only if the deployment threat model has expanded.

### PD8 — tiny restricted live, then gradual maturity

Live remains NO-GO until PD7 is separately accepted. If ever authorized, first live operation uses intentionally tiny capital and hard limits and expands only after observed stability.

### GUI track

GUI development may proceed in parallel as an inspection/control surface, but GUI never owns credentials, deterministic risk, durable trading truth, recovery, brokerage authority, or implicit live enablement.

## 11. Current effect non-authorizations

The roadmap pivot authorizes no production or account effects. Still not authorized:

```text
RETAINED_V1_STAGING_DELETE_OR_REPAIR
OLD_PUBLISHER_RERUN
NEW_PAPER_ROOT_CREATION
NEW_PAPER_STATE_MUTATION
ACL_MUTATION
ACCOUNT_CREATION_OR_MUTATION
WINDOWS_GROUP_MUTATION
PASSWORD_PROMPT
LSA_POLICY_OR_RIGHTS_MUTATION
KSP_KEY_OR_SIGNATURE_OPERATIONS
PROVIDER_CALL_7
BROKER_ORDER_SUBMISSION
LIVE_TRADING
```

Production recovery under the old v1 line remains blocked.

## 12. Next-chat resume procedure

1. Read `docs/architecture/102-personal-desktop-security-profile.md`, this handoff, and `docs/PROJECT_STATUS.md`.
2. Treat `feature/personal-desktop-paper-runtime` as the primary product branch; its base is accepted P2 `a810122a...`.
3. Do not assume a local personal-desktop worktree exists. Create/choose a fresh dedicated worktree only when moving into PD1 implementation, then prove root/branch/HEAD/clean state.
4. Leave `feature/p3-r1-recovery-implementation` and `F:\AI\worktrees\ai-trading-bot-p3-r1` preserved as the historical high-assurance line.
5. Do not continue Architecture-101 Gate 5B or modify Windows LSA policy merely to clear `SeBatchLogonRight`.
6. Do not touch `F:\AITradingBot\.Paper.provisioning-v1` or rerun the old publisher.
7. **Next milestone: PD1 architecture/design for the new versioned personal-desktop paper-account authority.** Freeze that contract before any source implementation or filesystem effect.
8. Include the next milestone in every verification/closeout report.
