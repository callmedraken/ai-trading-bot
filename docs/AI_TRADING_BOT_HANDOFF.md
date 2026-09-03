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
**Accepted PD1C source:** `e7c2ccbc21972f28b0e82622b426459c67b8007c`  
**PD1 real-host ACL correction:** `a58f231a7bf01ef2556c0f11f599d02e1a01f7c`  
**PD1E-C exact source freeze:** `da1807bcbccfcd07b552b6ae6bbd0fc3b1b1150e`  
**Current tree before this docs closeout:** `666147f4bedb754a60fbae6778360b08f5a00cc3`  
**Historical high-assurance branch:** `feature/p3-r1-recovery-implementation`  
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

**Tiny scoped status/handoff/docs closeouts are a ChatGPT-direct task by default. Do not delegate them to Codex unless there is a concrete implementation or tooling reason.**

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
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Production identity/path facts:

```text
host: DESKTOP-I4DOKM7
creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
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

### Accepted authority split

```text
Trading runtime plane
  genuine process-local ValidatedProductionAuthority + P2
  -> prepares/revalidates exact bundle during readiness

Administrator publication plane
  complete Administrator C1 installation-conformance evidence
  + exact source-owned PD1E publication freeze
  -> publication admission
```

A Trading runtime capability/P2 permit is never transferred into Administrator. `PersonalDesktopPaperPublicationFreeze` is immutable reviewed data, not a capability.

### PD1 implementation history

PD1A — **ACCEPTED**:

```text
fa16eef106638e5d6441a05b7f0dd5f757a63e53
```

PD1B — **ACCEPTED**:

```text
1390a16be5f16f7f38757c875a4648f7ef414d70
```

PD1C — **ACCEPTED**:

```text
e7c2ccbc21972f28b0e82622b426459c67b8007c
tree d14a986f63a600a8b17bef37c56df332c3b3b88c
```

PD1C provides the production-disabled publisher, disposable publication harness, source-owned publication-freeze contract, and corrected Trading-vs-Administrator authority split.

### Real-host VOLUME ACL correction

PD1E readiness exposed an over-strict PD1B rule on the actual `F:\` DACL. The effective ordinary non-admin ACEs were already safe, but Windows also exposed `INHERIT_ONLY` templates with generic masks. The governed immediate parent `F:\AITradingBot` is independently Administrators-owned with a protected DACL containing only Administrators and SYSTEM full control.

Accepted correction:

```text
commit: a58f231a7bf01ef2556c0f11f599d02e1a01f7c7
tree:   74d9d3f29c76a10261632d531fdfe9f786a336a7
```

Only the `VOLUME` role accepts ordinary-allow `INHERIT_ONLY` templates with supported inheritance flags. Their masks do not count as effective rights and cannot satisfy effective Admin/SYSTEM control. The immediate `PARENT` role remains strict.

Focused correction evidence:

```text
399 passed
Ruff check: PASS
Ruff format --check: PASS
diff checks: PASS
```

Broad re-certification at the corrected source:

```text
4151 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (417 files)
git diff --check: PASS
final HEAD: a58f231a7bf01ef2556c0f11f599d02e1a01f7c7
final tree: 74d9d3f29c76a10261632d531fdfe9f786a336a7
final worktree status: clean
```

### PD1E-A — Trading/C1/P2 exact bundle readiness — PASS

Run under:

```text
DESKTOP-I4DOKM7\Trading
```

The genuine C1/P2 read re-established accepted call-#6 provenance with:

```text
provider_call_performed = false
database_mutation_performed = false
```

Selected opening cash:

```text
Decimal("25000")
```

Derived immutable account evidence:

```text
paper_account_id:
  9415cd7b-bf36-5fba-bd58-a0f99119dc21

GENESIS checkpoint_id:
  1832a2b5-8b63-501a-8f7d-f1722c32307b
GENESIS SHA-256:
  d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548
GENESIS length:
  533

anchor SHA-256:
  16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85
anchor length:
  465

manifest SHA-256:
  8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029
manifest length:
  532
```

GENESIS `as_of` is exactly call-#6 `captured_at`:

```text
2026-08-29T09:46:43.769105+00:00
```

### PD1E-B — Administrator/C1/parent/occupancy readiness — PASS

Run under elevated:

```text
DESKTOP-I4DOKM7\John
```

Accepted Administrator token/C1 evidence:

```text
primary token: true
thread_token_present: false
elevated: true
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
approved Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
database_state: INITIALIZED_SUPPORTED
```

Read-only fixed-parent/occupancy evidence:

```text
F:\ fixed local NTFS/persistent-ACL volume: PASS
F:\AITradingBot protected Administrators/SYSTEM parent: PASS
v1 final present: false
v1 retained staging present: true
v2 final present: false
v2 staging present: false
```

The Administrator plane independently reconciled the same exact `$25,000` freeze candidate as the Trading plane.

### PD1E-C — exact source-owned freeze — ACCEPTED

Commit:

```text
da1807bcbccfcd07b552b6ae6bbd0fc3b1b1150e
tree 666147f4bedb754a60fbae6778360b08f5a00cc3
```

Exact source-owned freeze:

```text
machine_authority_id = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
approved_trading_sid = "S-1-5-21-1397534616-3988210162-180023805-1009"
paper_account_id = "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
starting_cash = Decimal("25000")
genesis_as_of = datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)
genesis_sha256 = "d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548"
genesis_byte_length = 533
anchor_sha256 = "16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85"
anchor_byte_length = 465
manifest_sha256 = "8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029"
manifest_byte_length = 532
```

Focused freeze verification:

```text
514 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
git diff --cached --check: PASS
```

The exact GitHub diff was accepted. It changes only the source freeze plus freeze/publication tests. It adds no loader, environment override, setter, CLI selection, runtime capability transfer, production path override, or publication effect.

Current source state is:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE = exact configured immutable PD1E freeze
```

Because the effect gate remains false, the configured freeze does **not** authorize or perform production publication.

### Certification state

```text
PD1_ARCHITECTURE_ACCEPTED = YES
PD1_SOURCE_ACCEPTED = YES
PD1_SOURCE_CERTIFIED = YES
PD1_PRODUCTION_READY = NOT YET FINALIZED
PD1_V2_PUBLISHED = NO
```

Certification at current head is based on the broad `4151 passed / 17 skipped` certification of the immediate parent `a58f231...`, followed by exact review and 514 focused tests for the immutable freeze-only `da1807b...` checkpoint. A second full-suite run was intentionally not required for that data-only change.

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
  PD1D source certification                                COMPLETE
  PD1E-A Trading/P2 exact bundle readiness                  PASS
  PD1E-B Administrator/C1/parent/occupancy readiness        PASS
  PD1E-C source-owned exact bundle freeze                   ACCEPTED
  PD1E-D final production-effect decision/publication       NEXT
PD2  reliable supervised manual paper cycle
PD3  supervised crash/recovery validation
PD4  unattended simulated paper under Trading
PD5  broker-paper integration
PD6  broker-paper soak / operational hardening
PD7  personal-desktop live-readiness
PD8  tiny restricted live -> gradual maturity
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

Production/live remains NO-GO.

## 12. Next-session / next-step procedure

1. Use only `F:\AI\worktrees\ai-trading-bot-personal-desktop` on `feature/personal-desktop-paper-runtime`.
2. Prove worktree/branch/HEAD/tree/clean state and fast-forward the latest docs-only checkpoint if local is behind remote.
3. Perform **one final read-only Administrator admission using the actual configured source freeze**, not a separately constructed candidate.
4. Reconfirm exact current C1 machine/SID evidence, protected fixed parent, `v2 final=false`, `v2 staging=false`, and retained v1 state without mutation.
5. Keep `PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=False` throughout that check.
6. If that final source-bound admission passes, ChatGPT/Sol reviews and presents the exact one-line effect-gate enablement diff and one-shot publication procedure.
7. Do **not** apply the enablement diff or run production publication without a separate explicit user authorization.
8. After a successful one-shot publication, independently reopen/reverify the final root before marking `PD1_V2_PUBLISHED=YES`.
9. Only then move to PD2 supervised manual paper-cycle composition.
10. Include the next milestone in every verification report.
