# PD1 completion: personal-desktop paper-account authority v2

## Status

PD1 is complete for the Architecture-102 closed single-owner Windows desktop profile.

```text
PD1_ARCHITECTURE_ACCEPTED    = YES
PD1_SOURCE_ACCEPTED          = YES
PD1_SOURCE_CERTIFIED         = YES
PD1_PRODUCTION_READY         = YES
PD1_V2_PUBLISHED             = YES
PD1_TRADING_RUNTIME_VERIFIED = YES
PD1                          = COMPLETE
```

This establishes only a simulated paper-account authority. Production/live trading remains NO-GO. No broker submission, provider call #7, unattended scheduling, live arming, v1 recovery, account/group/password change, LSA-policy change, or KSP/signing effect is authorized by this closeout.

## Accepted source line

Branch/worktree:

```text
feature/personal-desktop-paper-runtime
F:\AI\worktrees\ai-trading-bot-personal-desktop
```

Final accepted PD1 production-read correction:

```text
commit: a353d58230b5b37231d00e7799fa828ddf31bf30
tree:   db750395e9a4a837269c1b93befea453ed604380
message: fix: admit protected paper parent runtime
```

The correction preserves the Administrator/SYSTEM-only protected `F:\AITradingBot` parent while allowing the exact non-admin Trading process to verify the fixed `Paper-v2` authority directly. Trading does not list or pin the protected parent. A source-owned zero-access/no-follow fixed-name probe checks `F:\AITradingBot\.Paper-v2.provisioning` before and after the bounded account read; only exact file/path-not-found establishes staging absence. All normal root/anchor/GENESIS/runtime ACL, identity, independent-reopen, byte, Architecture-61, Architecture-66, receipt, and token checks remain fail closed.

Both production effect gates are contained:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

Production freeze blob remains:

```text
b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

## Fixed published account

```text
host:                 DESKTOP-I4DOKM7
Trading SID:          S-1-5-21-1397534616-3988210162-180023805-1009
machine_authority_id: 223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1
paper_account_id:     9415cd7b-bf36-5fba-bd58-a0f99119dc21
GENESIS checkpoint:   1832a2b5-8b63-501a-8f7d-f1722c32307b
starting cash:        Decimal("25000")
GENESIS as_of:        2026-08-29T09:46:43.769105+00:00
```

Exact frozen artifacts:

```text
GENESIS  SHA-256 d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548  length 533
anchor   SHA-256 16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85  length 465
manifest SHA-256 8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029  length 532
```

Durable occupancy after recovery publication:

```text
F:\AITradingBot\Paper-v2                    PRESENT / VERIFIED
F:\AITradingBot\.Paper-v2.provisioning      ABSENT
F:\AITradingBot\Paper                       ABSENT
F:\AITradingBot\.Paper.provisioning-v1      PRESENT / RETAINED / UNTOUCHED
```

The retained failed v1 staging tree remains historical evidence. Never rerun the old v1 publisher or delete, repair, rename, migrate, or reuse that tree as incidental cleanup.

## PD1E production/recovery history

```text
PD1E-D source-bound Administrator admission             PASS
PD1E-E publication source enablement                    ACCEPTED
  f4a3a697d2c35cd1efee1037862297e76c80161e

PD1E-F original production publication                  CONSUMED / BLOCKED
  failure phase: staged-verify
  v2 final absent / v2 staging present

read-only forensic qualification                        EXACT CANDIDATE

PD1E-FR1 publication parent/provenance correction       ACCEPTED
  c71147e62858fb0e494828efb52ab91a78027059
  301ecee4767d035ad032f5bb6e4d81d6e5edb1ce

PD1E-FR2 read-only recovery qualification source        ACCEPTED
  a28c3b8b74c0dc80b07dee1c50735f7998e39b26
PD1E-FR2 real-host qualification                        PASS

PD1E-FR3A recovery finalizer source                     ACCEPTED
  3cfc9e8aa8f6d25590abdfc82f6617a52e18dbf2

PD1E-FR3B recovery source enablement                    ACCEPTED
  7e616b0ac2a43d59f4b9c0e879cf2bccbd8c9b97

PD1E-FR3C one-shot real-host no-clobber recovery        SUCCESS
  status: FINALIZED_AND_VERIFIED
  phase: COMPLETE
  state: FINAL_REQUIRES_VALIDATION
  rename_may_have_begun: true
  failure_type: null
  exit code: 0

PD1E-FR3C-R1 immediate recovery re-containment          ACCEPTED
  085ddfc0852d7d23eaba93f41cfcb3247db28537
  both effect gates False

initial FR3D genuine Trading read                       BLOCKED
  genuine Trading C1 acquisition passed
  runtime read exposed protected-parent access mismatch

PD1E-FR3D-R1 protected-parent runtime correction        ACCEPTED
  a353d58230b5b37231d00e7799fa828ddf31bf30

final FR3D genuine Trading-account verification         PASS
  Trading SID exact
  non-admin / non-elevated
  paper_account_id exact
  GENESIS exact
  starting_cash 25000
  lineage_edge_count 0
  successors/reports/snapshots/receipts all 0
  operation_root F:\AITradingBot\Paper-v2\runtime
  both effect gates False
  exit code 0
```

The FR3D-R1 root cause was a source/design mismatch, not a host-ACL defect: Architecture 103 protects `F:\AITradingBot` from ordinary Trading access, but the original Trading reader recursively pinned that parent. The accepted correction keeps the protected parent unchanged and narrows Trading to source-owned fixed authority roots plus repeated fixed staging-absence observation.

## Final certification

Broad certification at the accepted FR3D-R1 source:

```text
4686 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (402 files)
git diff --check: PASS
final HEAD: a353d58230b5b37231d00e7799fa828ddf31bf30
final tree: db750395e9a4a837269c1b93befea453ed604380
final worktree: clean
```

The 17 skips are the expected opt-in Windows acceptance/native tests, unavailable symlink cases, and non-Windows fail-closed/import-safety assertions; no unexpected failure remains.

## Next milestone: PD2

PD2 is the reliable supervised manual paper-cycle milestone.

Before any Architecture-67 mutation under `Paper-v2\runtime`, implement and certify an account-scoped exclusive Windows mutex whose identity is deterministically derived from the exact `paper_account_id` under a source-owned namespace. Acquisition must be bounded and fail closed; the mutex does not create account authority. It must be held from authoritative account inspection through execution, durable transition commitment, and receipt commitment/recovery.

Recommended first slice:

```text
PD2A source-only account-scoped Windows mutex + admission contract
```

PD2A must perform no production paper-state mutation. Actual supervised Paper-v2 mutation remains a later separately reviewed PD2 effect checkpoint.
