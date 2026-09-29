# Architecture 128 — Clean D10 Redeployment and Reactivation After Halted Soak

Status: frozen design-only successor to Architecture 127. This document
authorizes no signing, protected filesystem mutation, Task Scheduler mutation,
activation publication, provider effect, Paper-v2 effect, broker-paper effect,
or live-trading effect.

## 1. Purpose

Architecture 127 source certification closes the durable-wake-evidence defect
that forced the first D10 soak to be halted before its first accepted natural
wake.

The old soak must never be resumed. Architecture 128 defines one clean
replacement lineage:

1. preserve the entire halted S5-R10 production deployment and final activation
   lease as immutable incident evidence;
2. build and sign a new sealed D10 deployment from the exact Architecture-127
   E6-certified executable source;
3. replace the disabled canonical D10 deployment without executing governed
   source;
4. qualify the new deployment under the actual Trading principal;
5. create a completely new bounded activation/soak and its empty append-only
   evidence object;
6. update and independently read back the scheduler contract while effects
   remain fail-closed;
7. publish the new final activation lease as the arming action;
8. observe the first natural scheduled wake. No manual start is part of this
   architecture.

This is a one-time recovery/redeployment contract, not a generic updater.

## 2. Certified source boundary

The new deployment material must be constructed from exactly the
Architecture-127 E6-certified repository identity:

```text
certified source HEAD:
0f9551e13486ef65b35a5a9633da19081571144b

certified source TREE:
1186e92669af100542c055368c1b72495c36bc11

certification evidence:
F:\AI\temp\pytest\arch127-e6-certification-20260929-010726
```

Later docs-only commits do not redefine the certified executable deployment.
The material builder must prove the exact certified HEAD/tree and governed Git
blob bytes under the existing Architecture-123/124 byte-exact construction
rules.

The new deployment ID, executable-manifest digest, launch-guard digest,
unsigned-attestation digest, detached-signature digest, activation timestamp,
end timestamp, and soak ID are deliberately NOT frozen here. They must be
derived from the exact certified bytes and later protected activation facts,
then reviewed before use. No caller may supply or override them.

## 3. Halted incident predecessor that must be preserved

Current production authority is fail-closed and historical:

```text
canonical old deployment:
S5-R10 deployment_id
9f3d111b-25bb-5ee4-9abf-f5215a32b826

signed attestation SHA-256:
4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2

old activation:
2026-09-29T00:45:22Z

old end:
2026-10-06T00:45:22Z

old soak_id:
48f14b13-aa18-5ce8-a0e0-402c867b17b6

old final activation-lease SHA-256:
91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84

halted task XML SHA-256:
8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0

task:
disabled and non-running

first accepted natural D10 wake:
none
```

The old activation lease is not cleanup debris. It is incident evidence.
Architecture 128 must never delete, overwrite, truncate, rewrite, reuse, or
reactivate it.

The previously retained S5-R8 retired deployment also remains untouched.

## 4. Namespace lineage

The existing canonical root remains:

```text
F:\AITradingBot\D10
```

The halted S5-R10 canonical root is retired whole, including its final activation
lease, to the fixed incident root:

```text
F:\AITradingBot\D10.retired-9f3d111b-25bb-5ee4-9abf-f5215a32b826
```

The new staging root is derived only from the reviewed new deployment ID:

```text
F:\AITradingBot\D10.replacement-<new-deployment-id>.installing
```

The existing historical S5-R8 retired root is not renamed or reused.

All three Architecture-128 roots must remain below the exact protected
`F:\AITradingBot` parent, on the same local NTFS volume, with the accepted
Architecture-124/125 native path, owner, DACL, no-reparse, link, and replacement
denial rules.

No replace-existing rename is permitted.

## 5. New inert deployment payload

Before the old canonical root is touched, the source-owned replacement operator
constructs and verifies the complete new inert deployment under the fixed
staging root.

It contains:

- the exact E6-certified sealed source snapshot;
- the exact E6-certified launch guard;
- the new canonical executable manifest;
- the new signed deployment attestation and detached signature;
- the fixed Architecture-127 evidence directory;
- no activation lease final/installing/tmp object;
- no current-soak evidence file;
- no `no-pycache` object or alternate bytecode/cache artifact.

The evidence directory is created with the exact Architecture-127 policy, but
the lease-derived evidence file is deferred until the new activation facts and
soak ID exist.

Staging verification must independently prove the signed deployment identity,
complete governed inventory, exact guard hash, trust material, Python/scheduler
bindings, evidence-root security, and all reserved-name absence before any
rename.

## 6. Protected deployment replacement ordering

Protected replacement is allowed only after a fresh read-only admission proves:

- elevated Administrator operator identity;
- exact protected parent/runtime substrate;
- exact old S5-R10 canonical deployment;
- exact old final activation lease and incident identity;
- exact disabled/non-running D10 scheduler contract;
- exact retained S5-R8 retired root;
- new S5-R10 retired destination absent;
- exact reviewed new staging deployment present;
- no conflicting reserved names;
- no governed source/provider/Paper-v2/broker/live effect in progress.

The protected mutation is at most these two fixed no-replace same-parent
renames, in order:

```text
1. F:\AITradingBot\D10
   -> F:\AITradingBot\D10.retired-9f3d111b-25bb-5ee4-9abf-f5215a32b826

2. F:\AITradingBot\D10.replacement-<new-deployment-id>.installing
   -> F:\AITradingBot\D10
```

The scheduler must remain disabled throughout replacement.

Every native mutation result is followed by fresh read-only namespace
classification. No automatic retry, rollback, delete, repair, or cleanup is
authorized. Ambiguous native completion stops for reconciliation.

A successful replacement leaves:

- new signed Architecture-127 deployment at canonical D10;
- halted S5-R10 deployment + old lease at its fixed retired incident root;
- historical S5-R8 retired root untouched;
- new canonical activation lease absent;
- new evidence directory present but no current-soak file;
- scheduler still disabled/non-running.

## 7. Post-replacement Trading qualification

Before reactivation design may cross into protected activation, the actual
non-admin Trading principal must perform a read-only qualification of the new
canonical deployment.

It must prove:

- signed new deployment and exact sealed source/guard;
- protected production Python substrate;
- exact evidence-root identity/security;
- activation lease final/installing/tmp absent;
- current-soak evidence file absent because no new soak exists yet;
- second-stage launch trapped/not called;
- scheduler/provider/Paper-v2/broker/live effects not run.

Failure leaves the task disabled and the deployment inert.

## 8. New activation and evidence identity

The old activation/end/soak ID can never be reused.

A later reviewed source-owned reactivation operator freezes one new UTC
activation instant and derives:

- exact activation + seven-day end;
- exact new activation lease;
- exact new soak ID under the existing deterministic lease model;
- exact lease-derived evidence path:

```text
F:\AITradingBot\D10\evidence\wake-<new-soak-id>.jsonl
```

The evidence path is never a caller argument.

Before the new final activation lease exists, an elevated protected
provisioning step must create exactly that evidence file as an empty regular
file with Architecture-127's accepted policy:

- Administrators owner / protected DACL;
- Trading read + `FILE_APPEND_DATA` and required metadata/control access;
- no `FILE_WRITE_DATA`, delete, rename, `WRITE_DAC`, or `WRITE_OWNER`;
- local NTFS, non-reparse, single-link;
- fixed final path;
- zero bytes.

The operator must verify that the real Trading token can open the exact file
with the Architecture-127 append-only WRITE_THROUGH access/flag contract
without writing any record.

An orphaned evidence object after an interrupted activation attempt grants no
authority. It must be preserved and classified; no automatic cleanup or reuse
under newly derived activation facts is allowed.

## 9. Scheduler and lease reactivation ordering

Reactivation preserves the established fail-closed P124-5 principle: the final
activation lease is the arming action.

After evidence-file verification and while the final lease remains absent:

1. re-prove exact new signed deployment and empty exact evidence file;
2. acquire any required scheduler credential through the existing interactive
   boundary;
3. perform a fresh read-only admission after that pause;
4. update exactly the disabled existing D10 task to the new seven-day
   activation/end contract while preserving the exact sealed-guard action,
   zero semantic arguments, working directory, retry/overlap policy, and other
   frozen scheduler fields;
5. independently read back the scheduler through the Architecture-126 COM-first
   observer;
6. re-prove deployment, evidence file, and lease absence;
7. publish the exact new activation lease through the existing create-only
   `.tmp -> .installing -> final` no-replace protocol;
8. independently reread deployment, scheduler, final lease, and still-empty
   evidence file.

If the scheduler becomes enabled before final lease publication, the guard
remains fail-closed because the lease is absent. No manual task start is
authorized.

If any scheduler or lease mutation is ambiguous, stop and perform read-only
reconciliation. No automatic retry or rollback is authorized.

## 10. First wake and soak continuation

Successful final lease publication produces a new D10 armed state only. It is
not D10-C acceptance.

The next checkpoint is the first natural scheduled wake. Do not manually start
the task.

D10-C acceptance requires the exact current-soak Architecture-127 observer to
show a valid durable wake sequence, including the guard-owned WAKE_START and,
for a nonterminal result, the matching ACCEPT record.

Only after that first natural wake is accepted may normal D10-D observation
continue. Any terminal/incomplete/unaccepted durable evidence latches the new
soak stopped. There is no automatic restart, extension, or replacement soak.

## 11. Checkpoints and authorization boundaries

Architecture 128 is divided into these checkpoints:

```text
R1  source-only E6 material construction
R2  exact material review + separate signing authorization
R3  read-only halted-host/replacement preflight
R4  protected deployment replacement              EXPLICIT AUTHORIZATION
R5  non-admin Trading read-only deployment qualification
R6  source-only evidence/reactivation operator + focused verification
R7  protected evidence + scheduler + lease activation EXPLICIT AUTHORIZATION
R8  first natural D10-C wake observation
```

R1, design work, source tests, and repository review authorize no protected
host mutation.

R2 signing, R4 replacement, and R7 evidence/scheduler/lease mutation each
require their own explicit authorization. Authorization for one does not imply
authorization for another.

No Architecture-128 checkpoint authorizes broker-paper or live trading.

## 12. Acceptance criteria for the design/source phases

Before protected work can be proposed, source/tests must prove at minimum:

- exact E6 certified source pin and byte-exact governed material construction;
- old halted deployment/lease identity is source-owned and cannot be caller
  substituted;
- old lease and old soak can never authorize new deployment bytes;
- fixed new staging and old-retired namespace derivation;
- disabled/non-running scheduler required for replacement;
- exact two-rename no-replace replacement ordering and recovery
  classification;
- no automatic retry/rollback/cleanup;
- evidence directory in new deployment with exact Architecture-127 policy;
- new evidence file derived only from new verified lease/soak;
- evidence file created empty before final lease;
- Trading append-only WRITE_THROUGH open succeeds without FILE_WRITE_DATA;
- scheduler readback precedes final lease;
- final lease remains the arming action;
- old activation/end/soak ID reuse rejected;
- first natural wake required; manual start absent;
- provider/Paper-v2/broker/live effects remain closed during deployment and
  activation plumbing.
