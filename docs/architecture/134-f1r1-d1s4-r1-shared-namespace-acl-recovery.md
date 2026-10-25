# Architecture 134-F1R1-D1S4-R1 — Shared Namespace ACL Recovery

Status: IMPLEMENTED SOURCE; pending first publication, canonical CI and ChatGPT
exact-source review. No real R1 preflight or protected recovery ran here.
Final source identity: PENDING FINAL COMMIT.
Terminal CI: PENDING FIRST/ONLY PUSH.

## Accepted base and frozen incident

Accepted/integrated D1S4 source and required R1 direct parent:

    HEAD 30a410d9023324ebe5c23e6a8ff128353b9ebf1f
    TREE cf50b0b7b84428d9e502ed5bd85307001bc866ed

Both remote develop and the accepted D1S4 branch were verified at this identity.
The stale main checkout was used only for fetch/admission and isolated worktree
creation; its branch, index, tracked files and unrelated artifacts were preserved.

The one-shot direct installation completed PASS / DIRECT_INSTALL_VERIFIED /
CONFIRMED / IDENTITY_STABLE=True for
`release-18d5d329c1d458558e98d7effe523c3b`. Its D1S4 attempt is permanently
consumed. A later fresh read-only preflight was BLOCKED /
READ_ONLY_ADMISSION_REJECTED / IDENTITY_STABLE=True. Source reconstruction,
Administrator admission, replay and the consumed D1S4 latch were valid. The
middle namespace ancestor had acquired a non-system write ACE externally.

Exact drift principal: DESKTOP-I4DOKM7\John,
`S-1-5-21-1397534616-3988210162-180023805-1005`.

Only these two protected Administrators-owned, local NTFS, non-reparse directories
are repair targets, in this frozen mutation order:

| Target | Identity | Pre-descriptor SHA-256 |
| --- | --- | --- |
| F:\AITradingBot | (1855336320, 1125899907973390) | 292a285f86a102698ab1b212a998d18178ba4c7e8cbe0c25ac195a747fb944d9 |
| F:\AITradingBot\releases | (1855336320, 281474980511321) | 7113305203979cd4dd63a92a5239e9de9e2d4de0212610c149ef834babbee6de |

The only admitted pre-policy for each target is its target tuple followed by
exactly `(drift_sid, 2032127, 0, 3)`, in that order. The tuple fields are SID,
mask, ACE type and flags. No extra/missing/reordered ACE is accepted.

Exact post-policy for F:\AITradingBot is current ADMIN_ACES:

    ('S-1-5-32-544', 0x1F01FF, 0, 0)
    ('S-1-5-18',     0x1F01FF, 0, 0)

Exact post-policy for F:\AITradingBot\releases is D1S4 IMAGE_ACES:

    ('S-1-5-32-544', 0x1F01FF, 0, 0)
    ('S-1-5-18',     0x1F01FF, 0, 0)
    ('S-1-5-21-1397534616-3988210162-180023805-1009', 0x1200A9, 0, 0)

Owner remains Administrators and both DACLs remain protected. ROOT_ACES and
Architecture-133 retained-root recovery are historical reference only and are
not reachable mutation paths. No arbitrary SID-removal or ACL editor exists.

## Preserved scope and trust

The observer opens only the volume, both exact targets, runtime, production
python.exe and the following three exact release roots. It never enumerates or
recursively walks a descendant namespace.

| Preserved release object under releases | John ACE |
| --- | --- |
| release-18d5d329c1d458558e98d7effe523c3b | present |
| release-cb94451fc3295a97afffe9fac5d09ff3.installing | present |
| release-03c42597246752319956ab96e01ed61c.installing | absent |

All three objects must exist as protected, non-reparse NTFS directories. Runtime
and production Python must exist with no John ACE or non-system write policy.
Their current identities and owner/DACL descriptor hashes, plus the volume
observation, are bound into the reviewed plan and compared after effect. The
fixed observer does not claim byte-level replay of these incident images.

None of these release roots is repaired, renamed, deleted, rewritten, promoted,
recycled or reused. R1 results and plans explicitly set runtime_binding_eligible
and successor_soak_eligible to false, including on success. Repairing shared
parents cannot restore trust in the compromised D1S4 FINAL. A future successor
requires a new source checkpoint, HEAD/TREE and deterministic release ID/path.
That installation is outside R1.

## Read-only plan and one-shot authority

Registered checkpoint:
`arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery`.

`src/trading_bot/shared_namespace_acl_recovery.py` owns clean exact source/base/origin/live remote
admission, enabled elevated Administrator admission, fixed observation,
canonical plan and durable latch. Source interlocks are
`AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_ACCEPTED_HEAD` and
`AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_ACCEPTED_TREE`.

The canonical sorted compact JSON plan binds schema, exact current HEAD/TREE,
two paths/identities/pre-hashes/pre-ACEs/target-ACEs, owner/protection/NTFS/reparse
expectations, drift SID, fixed mutation order, all non-target observations,
preserved release IDs/paths, and automatic_retry=NOT_AUTHORIZED. Unchanged host
and source yield identical semantic plan and SHA-256. Preflight writes no latch
or production object; the runner may write ordinary external evidence.

Execute requires both:

    AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_REVIEWED_PLAN_SHA256
      = exact reviewed lowercase 64-hex plan digest
    AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_ACL_RECOVERY_AUTHORIZATION
      = ARCH134_F1R1_D1S4_R1_ONE_SHARED_NAMESPACE_ACL_RECOVERY_AUTHORIZED

Preflight PASS/source acceptance does not grant effect authority.

A new independent fixed latch is exclusively created at:

    F:\AI\temp\arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery-attempt.json

Its schema is the checkpoint name plus `-attempt/v1`. Canonical payload binds
source_head/tree, plan_sha256, both target identities/pre-descriptor hashes,
status=CONSUMED and automatic_retry=NOT_AUTHORIZED. It must be written fully,
flushed, fsynced, closed and read back exactly with matching created identity
before the mutation fence. A process lock and spent marker also close in-process
races/ambiguity. Any existing/malformed/unprovable latch blocks execution. No
D1S4, D1S3, R5 or Architecture-133 latch is reused or renewed.

## Isolated leaf namespace

The two new modules live directly under trading_bot rather than the suggested
supervised_release package. Its eager public facade imports release models,
strategies and provider-bearing market-data packages. R1 uses its own small
security-facts record and proven Windows ABI patterns, preserving the existing
release facade unchanged. The closed graph contains only these two leaf modules,
the pure top-level paper configuration and the proven read-only ACL/token helpers.
No strategy, release reconstruction, provider or runtime module is imported.

## Private native boundary and partial effects

`src/trading_bot/shared_namespace_acl_native.py` exposes no public ACL writer. `_PinnedTargets`
opens both fixed targets before reservation, using OPEN_EXISTING, no-follow,
read rights plus WRITE_DAC, and exclusive sharing. It reobserves the complete
accepted plan immediately before the mutation fence and each native call. The
only security mutation binding is SetSecurityInfo on the already held exact
handle. Native DACL material comes only from source-owned tuples. Flags are
DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION (0x80000004),
with owner/group/SACL pointers NULL. No owner rewrite or new grant occurs.

Exclusive directory opens are essential: removing an inheritable ACE can
otherwise propagate changes to descendants, even when replacement ACEs do not
inherit. Microsoft's [SetSecurityInfo contract](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo)
documents exclusive sharing as suppressing child propagation; its
[inheritance description](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces)
describes inherited-ACE removal. No propagation/tree-security API is invoked.
The three preserved roots also must remain inheritance barriers. Actual native
host acceptance is later protected qualification; fake tests do not claim it.

The outer target is attempted first, then releases. Stop after any failed,
false, nonzero or ambiguous call/readback; never roll back or retry. The native
session burns its step before invoking the API and retains each returned raw
DWORD even when descriptor freeing later fails. The operator attempts handle
readback regardless of return, closes all handles and attempts two independent
reopens even after native/close failure. Success requires both zero DWORDs,
identical repeated security evidence, unchanged identities, exact target tuples,
Administrators ownership/protection, NTFS/non-reparse, no John SID, unchanged
fixed non-targets, unchanged source and consumed exact latch.

Success: PASS / SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED / CONFIRMED /
IDENTITY_STABLE=True / AUTOMATIC_RETRY=NOT_AUTHORIZED. The latch remains consumed.
Any post-fence exception, interrupt, exit, close ambiguity or failed verification
returns terminal INDETERMINATE /
PRESERVE_SHARED_NAMESPACE_ACL_RECOVERY_EVIDENCE_NO_RETRY / MAY_HAVE_OCCURRED.

## Later read-only reconciliation

| Latch | Policy | Result | Execute eligible |
| --- | --- | --- | --- |
| AVAILABLE | exact frozen drift | PASS / READY_FOR_SHARED_NAMESPACE_ACL_RECOVERY | true |
| CONSUMED | both exact recovered targets | PASS / SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED | false |
| CONSUMED | exact original drift unchanged | BLOCKED / CONSUMED_ATTEMPT_NO_CONFIRMED_RECOVERY | false |
| consumed/unprovable | partial/mixed/unprovable | BLOCKED or INDETERMINATE / PARTIAL_OR_CONFLICTING_ACL_RECOVERY | false |
| AVAILABLE | baseline changed | BLOCKED / PRE_RECOVERY_BASELINE_DRIFT | false |

No state renews authority. R1 provides no installation or runtime dispatcher.

## D1S4 diagnostic correction and source enforcement

D1S4 preserves top-level READ_ONLY_ADMISSION_REJECTED/OBSERVATION_DRIFT behavior
while adding closed admission_stage/admission_code fields. Tests distinguish
SOURCE_ADMISSION, RELEASE_RECONSTRUCTION, ADMINISTRATOR_ADMISSION,
PARENT_OBSERVATION, PRODUCTION_PYTHON_OBSERVATION, NAMESPACE_ENUMERATION,
FINAL_OBJECT_OBSERVATION, ATTEMPT_OBSERVATION, FINAL_IMAGE_REPLAY and
REPEAT_ADMISSION. No arbitrary exception/native error text is serialized.

R1 authority overlays retain predecessor dictionaries and pin changes to exact
accepted blobs/AST. Import graph checks reject Architecture-133 recovery,
D1S3/R5, D1S4 execute, historical publication and unrelated operational effects.
An explicit native binding allowlist rejects additional/dynamic API bindings.
The exact branch maps to canonical CI ROBINHOOD under the existing reviewed
feature family, with source-static -> active-tests -> certification-tests ->
source-gates and unchanged 300-second ceiling. Required 122/49 baselines and
lane algorithms remain frozen; new current tests enter automatically.

No real R1/D1S4 preflight/execute, scheduler, runtime start, credential/provider,
paper/broker, D1/D2 or live effect is part of implementation. Live remains NO-GO.
Next owner: ChatGPT exact-source review, then reviewed integration/develop CI,
registered read-only R1 production preflight, separate protected review/one-shot
execute, registered reconciliation, and only if recovered a fresh successor.

Also remove or update any tests and docs that referenced the old behavior.
