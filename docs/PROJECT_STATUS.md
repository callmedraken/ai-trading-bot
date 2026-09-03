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

Primary product branch/worktree:

```text
feature/personal-desktop-paper-runtime
base: a810122a96b6fc90da25d71eede8da64b7272c98
F:\AI\worktrees\ai-trading-bot-personal-desktop
```

Personal-desktop docs checkpoints:

```text
Architecture 102 adoption: fab1d776abcdcbf09fb26a257ea7fc86f6201b26
Architecture 103 + validation plan: 12e41c4e407a79d63ea896773bf8462038ebba27
```

Accepted PD1 checkpoints:

```text
PD1A pure authority/bundle:
  fa16eef106638e5d6441a05b7f0dd5f757a63e53

PD1B read authority/security:
  1390a16be5f16f7f38757c875a4648f7ef414d70

PD1C corrected publisher/freeze architecture:
  e7c2ccbc21972f28b0e82622b426459c67b8007c
  tree d14a986f63a600a8b17bef37c56df332c3b3b88c

PD1B real-host volume-ACL compatibility correction:
  a58f231a7bf01ef2556c0f11f599d02e1a01f7c7
  tree 74d9d3f29c76a10261632d531fdfe9f786a336a7

PD1E-C exact source-owned production bundle freeze:
  da1807bcbccfcd07b552b6ae6bbd0fc3b1b1150e
  tree 666147f4bedb754a60fbae6778360b08f5a00cc3
```

```text
PD1_SOURCE_ACCEPTED = YES
PD1_SOURCE_CERTIFIED = YES
PD1_PRODUCTION_READY = NOT YET FINALIZED
PD1_V2_PUBLISHED = NO
```

The current-head certification basis is the exact reviewed PD1E-C diff on top of the broadly re-certified `a58f231...` parent plus its focused 514-test freeze/publication/security/provisioning regression gate. The full suite was intentionally not rerun for the immutable-data-only freeze checkpoint.

## Mandatory personal-desktop security baseline

The roadmap pivot reduces ceremony depth, not material trading safety. Mandatory controls remain:

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

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider effects are consumed. Call #5 is permanently `FAILED / CONFIRMED`. Call #6 is permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. Provider call #7 is not authorized.

Selected call #6:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
captured_at: 2026-08-29T09:46:43.769105+00:00
```

Production identities/paths:

```text
host: DESKTOP-I4DOKM7
creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
authority_epoch_id: e6f3de5d-1412-40ad-a022-8b33e72a5f6d
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

Fixed production paths:

```text
final authority root:       F:\AITradingBot\Paper-v2
provisioning staging root:  F:\AITradingBot\.Paper-v2.provisioning
Architecture-67 root:       F:\AITradingBot\Paper-v2\runtime
operation receipt parent:   F:\AITradingBot\Paper-v2\runtime\paper-operations
```

The accepted authority split is:

```text
Trading / non-admin plane
  genuine process-local ValidatedProductionAuthority + P2
  -> prepares/contextually verifies exact bundle during readiness

Administrator publication plane
  complete Administrator C1 installation-conformance evidence
  + reviewed source-owned PersonalDesktopPaperPublicationFreeze
  -> publication admission
```

`ValidatedProductionAuthority` and the P2 permit are never serialized or transferred into the Administrator process.

### PD1E exact production bundle freeze

Starting cash is now selected and frozen as:

```text
Decimal("25000")
```

Trading-plane readiness passed under `DESKTOP-I4DOKM7\Trading` using genuine C1/P2 evidence. No provider call and no authority-database mutation occurred.

Administrator-plane readiness passed under elevated `DESKTOP-I4DOKM7\John` with:

```text
primary token: true
thread impersonation: false
elevated: true
C1 database state: INITIALIZED_SUPPORTED
```

Read-only occupancy/security at readiness:

```text
F:\ volume: accepted after bounded VOLUME-only inherit-template correction
F:\AITradingBot: Administrators-owned, protected DACL, Administrators+SYSTEM full
v1 final: absent
v1 retained staging: present
v2 final: absent
v2 staging: absent
```

The exact source-owned freeze at `da1807b...` is:

```text
machine_authority_id = 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
approved_trading_sid = S-1-5-21-1397534616-3988210162-180023805-1009
paper_account_id = 9415cd7b-bf36-5fba-bd58-a0f99119dc21
starting_cash = Decimal("25000")
genesis_as_of = 2026-08-29T09:46:43.769105+00:00

genesis_sha256 = d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548
genesis_byte_length = 533

anchor_sha256 = 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85
anchor_byte_length = 465

manifest_sha256 = 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029
manifest_byte_length = 532
```

Current production source state:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE = configured exact immutable PD1E values
```

The configured freeze is data only and grants no publication authority while the effect gate remains false.

### Certification evidence

Initial PD1D broad certification:

```text
4117 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (417 files)
git diff --check: PASS
```

After the real-host VOLUME ACL compatibility correction, broad re-certification at `a58f231...` / tree `74d9d3...` passed:

```text
4151 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (417 files)
git diff --check: PASS
final HEAD/tree exact
final worktree clean
```

PD1E-C freeze-only focused verification at `da1807b...`:

```text
514 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
git diff --cached --check: PASS
production effects remained False
no production filesystem effect occurred
```

## Retained failed v1 publication

Historical state remains frozen:

```text
F:\AITradingBot\Paper                       absent
F:\AITradingBot\.Paper.provisioning-v1     retained historical staging
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

Never rerun the old publisher or delete/repair/rename/migrate/reuse the retained v1 staging tree.

## High-assurance P3-R1 line — preserved, parked, optional

```text
branch: feature/p3-r1-recovery-implementation
remote head: 45e5b745c9dca63d69dbb9c2032cd29d3731f27a
Architecture-101 source: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
Architecture-101 tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
```

```text
ARCHITECTURE_101_HIGH_ASSURANCE_READINESS=BLOCKED
PERSONAL_DESKTOP_PRODUCT_ROADMAP=NOT_BLOCKED_BY_THIS_FINDING
```

Do not change host LSA policy merely to satisfy this parked gate.

## Revised primary roadmap

```text
PD0  personal-desktop profile adoption                     COMPLETE
PD1  personal-desktop paper-account authority v2           CURRENT
  PD1A pure anchor/account-ID/provisioning bundle           ACCEPTED
  PD1B Windows read-only authority + token/ACL/path         ACCEPTED
  PD1C disabled publisher + disposable publication tests   ACCEPTED
  PD1D exact diff review + broad source certification      COMPLETE
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

### PD1E-D next milestone

Before any production mutation, perform one final **read-only source-bound Administrator admission** against the configured freeze and current C1/parent/occupancy state. If it remains clean, ChatGPT/Sol may present the exact one-line production-effect enablement diff and one-shot publication procedure for a separate explicit user authorization.

PD1E-D is not authorized merely by reaching this checkpoint. Publication, ACL creation under `Paper-v2`, and the source effect-gate change remain separate explicit-effect decisions.

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
- **Tiny scoped status/handoff/docs closeouts are handled directly by ChatGPT by default.**
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
