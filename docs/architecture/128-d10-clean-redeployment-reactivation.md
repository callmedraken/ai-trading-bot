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

The historical S5-R8 retired deployment was already removed by the accepted P125-R1I cleanup and must remain absent.

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

R3 is read-only and therefore runs before any new staging object exists. It
must prove:

- elevated Administrator operator identity;
- exact protected parent and current halted D10 namespace;
- production runtime/Python substrate remains unchanged by R4 and is freshly requalified at R5 before any reactivation;
- exact old S5-R10 canonical deployment;
- exact old final activation lease and incident identity;
- exact disabled/non-running D10 scheduler contract;
- historical S5-R8 retired root absent, matching accepted P125-R1I cleanup evidence;
- new S5-R10 retired destination absent;
- new Architecture-128 staging destination absent;
- no conflicting reserved names;
- no governed source/provider/Paper-v2/broker/live effect in progress.

R4 begins only after a separately authorized protected action constructs and
verifies the complete signed new staging deployment at the fixed staging path.
After staging construction and before either rename, R4 must repeat the full
read-only admission above and additionally prove that the exact reviewed new
staging deployment is present. Only that post-staging admission can authorize
the two fixed renames.

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
- historical S5-R8 retired root remains absent;
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

### Architecture 128 R1 unsigned deployment material — ACCEPTED

The second R1 construction attempt passed from a fresh byte-exact detached
checkout of the exact Architecture-127 E6-certified executable source:

```text
certified source HEAD:
0f9551e13486ef65b35a5a9633da19081571144b

certified source TREE:
1186e92669af100542c055368c1b72495c36bc11

R1 byte-exact worktree:
F:\AI\worktrees\ai-trading-bot-d10-arch128-r1-0f9551e-byteexact-r2

R1 evidence:
F:\AI\temp\arch128-r1-material-r2-20260929-014734

status:
PASS

raw governed files:
308

raw governed mismatches:
0

executable manifest entries:
307

separately attested launch guard:
1

deployment_id:
d2071f25-5a7c-5293-a28f-5b722c9917a2

executable manifest SHA-256:
080c622035c7c8492a66ba5d5aa9a48c9020933fb16f85a7604010d529bd06e2

executable manifest byte length:
51724

total executable bytes:
5420008

unsigned attestation SHA-256:
3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71

unsigned attestation byte length:
1011

launch guard SHA-256:
ab80233a6ce59a579653008609753441864f74592ac52d12ec65c6dc714eabf7

launch guard byte length:
112228

signing key ID:
AITradingBot/D10/DeploymentAttestation/v3

summary SHA-256:
5a92e432c107bf5b091dc4da7984fb5f361dc570346fd0ed0503240963a27361
```

The builder and caller independently agreed on the summary, manifest, and
unsigned-attestation digests. The new deployment ID does not reuse the halted
S5-R10 deployment ID. Final HEAD/tree remained exact and the material checkout
remained clean.

The first R1 attempt remains preserved diagnostic evidence and is not reused:

```text
F:\AI\worktrees\ai-trading-bot-d10-arch128-r1-0f9551e-byteexact
F:\AI\temp\arch128-r1-material-20260929-013732
```

That attempt blocked only because its external preflight retained the historical
S5-R10 raw-governed count of 307. Architecture 127 legitimately added
`src/trading_bot/runtime/personal_desktop_d10_wake_evidence_log.py`, making
the E6 raw-governed count 308 while the manifest contains 307 entries because
the launch guard is separately attested.

No signing, production filesystem mutation, Task Scheduler mutation, provider,
Paper-v2, broker, or live effect occurred.

Next checkpoint: Architecture 128 R2 exact signing-material review. Actual use
of the production private signing identity remains a separate explicit
authorization boundary.

### Architecture 128 R2 pre-sign path correction — ACCEPTED

The first separately authorized R2 signing invocation stopped before any CNG
key qualification or signature operation. The operator had already created and
reported the external evidence directory:

```text
F:\AI\temp\arch128-r2-signing-20260929-090344-236569
```

and then failed with:

```text
R2 STOP: evidence_directory_invalid
```

The cause was source-only: the R2 validator used `type(evidence) is Path`.
On Windows, pathlib constructs a `WindowsPath` subclass, so the exact-type
check rejected the operator's own valid fixed evidence path before the code
reached:

- `qualify_existing_d10_signing_key_after_attempt2()`;
- `WindowsCngExternalSigner`;
- any NCrypt sign call.

Therefore the failed attempt consumed no signature operation and made no
production, scheduler, provider, Paper-v2, broker, or live effect. Preserve the
reported evidence directory as diagnostic evidence and never reuse it.

The correction is accepted at:

```text
HEAD:
e9d2a0f669a2b12f7fbb3eab560bf17d51b3c2eb

TREE:
dff1634435bd95f9a1cbea24d4e7d3eab5072d47
```

It replaces the exact-type check with `isinstance(evidence, Path)`, extracts
the evidence-directory validator, and adds regression coverage for platform
Path subclasses plus wrong-parent, wrong-prefix, and nonempty evidence
directories.

Focused correction verification:

```text
17 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
final HEAD/tree: exact
worktree: clean
```

The accepted R1 signing material is unchanged:

```text
deployment_id:
d2071f25-5a7c-5293-a28f-5b722c9917a2

unsigned attestation SHA-256:
3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71

unsigned attestation bytes:
1011

signing key ID:
AITradingBot/D10/DeploymentAttestation/v3
```

Because the protected signing operator source identity changed after the prior
authorization, the production-key signature requires fresh explicit
authorization bound to the corrected HEAD/tree. No protected retry is
authorized by this documentation closeout.

### Architecture 128 R3 read-only halted-host preflight — ACCEPTED

Exact reviewed R3 source:

```text
HEAD:
e38c85449ba206b73615758e33e76f8384001ceb

TREE:
568e2003d8c56c1f8a26c64e0ec7adf79e91f4ed
```

Source verification completed with 444 passing tests, Ruff check PASS, Ruff
format PASS, PowerShell parse PASS, git diff --check PASS, and AST-equivalent
formatter-only closeout.

The real elevated host observation then passed read-only:

```text
D10_ARCH128_R3_READONLY_PREFLIGHT=PASS
ARCH128_R3_OBSERVER_EXIT=0
D10_ARCH128_R3_HOST_PREFLIGHT=PASS

R3 result SHA-256:
171edaee0e972f394ce0e4a62e6d5e6f34b54e79f903feb6c057343b1dd4537d

wrapper summary SHA-256:
36149529b48cb5187f1b562e1c8f45b0f5345d7b24b8d019f0928ca9108ce100
```

R3 proved the exact halted signed S5-R10 deployment and old final lease remain
stable, the D10 task remains disabled/non-running, the accepted post-halt
scheduler state remains exact, the historical S5-R8 retired namespace remains
absent, the new S5-R10 incident-retirement destination is absent, and the new
Architecture-128 staging destination is absent.

Signing, production filesystem mutation, scheduler mutation, source launch,
provider, Paper-v2, broker, and live effects were NOT_RUN.

R3 is closed as ACCEPTED. The next checkpoint is R4 protected staging
construction plus deployment replacement. R4 requires separate explicit human
authorization before any protected filesystem mutation. R3 acceptance itself
authorizes no staging creation, rename, ACL mutation, scheduler mutation,
activation publication, provider/Paper-v2, broker, or live effect.

### Architecture 128 R4A pure replacement contract — ACCEPTED

R4A is accepted at:

```text
HEAD:
ced58725167806d79c6915f792dd65da99b9a49a

TREE:
21c7922c3afc8f70e55d86e34bfc91dc18b34850
```

Behavioral verification:

```text
121 tests passed
R4A effect surface: PURE_NO_IO
git diff --check: PASS
```

The final Ruff-only closeout was proven AST-equivalent to the tested behavior
source and then independently passed both required Ruff gates:

```text
ruff check --no-cache: PASS
ruff format --check --no-cache: PASS
AST equivalence: PASS
final worktree: clean
remote feature ref: exact
```

R4A freezes only pure Architecture-128 authority facts: exact halted S5-R10 and
new E6 signed identities, fixed canonical/staging/retired paths, valid namespace
states, all admission predicates, the exact two ordered no-replace rename
steps, and terminal indeterminate-mutation behavior. It contains no Windows
native API, filesystem I/O, scheduler API, credential, source-launch, provider,
Paper-v2, broker, or live effect surface.

Next checkpoint is R4B source-only implementation and review of the
Architecture-128-specific Windows staging/read-only-admission/rename adapter.
No protected filesystem mutation is authorized by R4A acceptance.

### Architecture 128 R4B Windows adapter — ACCEPTED

R4B is accepted at:

```text
HEAD:
3c3703f41524ac02fdaffc63b52082c51cdb2736

TREE:
f2ea820e7582d773f8d8cb668725bbb25661497c
```

The accepted source-only adapter provides:

- a create-only staging writer confined to the exact Architecture-128 staging
  root;
- no activation-lease creation path;
- no evidence-log file creation path;
- an inert empty `evidence` directory staging path only;
- a no-follow reader limited to canonical/new-staging/new-retired/historical
  retired fixed namespaces;
- exactly two parent-relative native rename paths:
  canonical -> new incident-retired and staging -> canonical;
- `replace_if_exists = 0`;
- terminal `INDETERMINATE` result on native status, completion, post-call
  identity, or handle-close ambiguity;
- no operator/CLI, scheduler, credential, provider, Paper-v2, broker, or live
  entry point.

The corrected R4B gate passed its focused Architecture-128 tests plus the
existing protected-deployment/replacement regressions and then passed both
required Ruff commands independently before the final decision.

R4B acceptance authorizes no production invocation. The next checkpoint is R4C
source-only construction/orchestration: reconstruct the exact E6 material from
the byte-exact R1 worktree, cross-check the accepted R1 manifest/attestation and
R2 detached signature, construct the inert signed staging payload through an
injected backend, perform a fresh post-staging read-only admission, and expose
only an in-process two-step rename session. Protected execution remains a
separate explicit R4 authorization boundary.

