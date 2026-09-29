# PD4 D10 Architecture 128 Clean Redeployment / Reactivation Validation Plan

Status: source/design-only validation plan. No protected production mutation is
authorized by this document.

## Accepted predecessor

Architecture 127 E6 passed at:

```text
HEAD  0f9551e13486ef65b35a5a9633da19081571144b
TREE  1186e92669af100542c055368c1b72495c36bc11
9178 cases / 9161 passed / 17 skipped / 0 failed / 0 errors
evidence:
F:\AI\temp\pytest\arch127-e6-certification-20260929-010726
```

Production remains halted:

```text
old deployment_id:
9f3d111b-25bb-5ee4-9abf-f5215a32b826
old soak_id:
48f14b13-aa18-5ce8-a0e0-402c867b17b6
old lease SHA-256:
91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84
task:
disabled / non-running
first accepted natural wake:
none
```

Never resume the old soak.

## R1 — source-only new deployment material

- construct canonical executable manifest and unsigned deployment attestation
  from exact E6-certified HEAD/tree in a byte-exact checkout;
- include Architecture-127 launch guard/source bytes and evidence-root contract;
- emit only public bytes/digests/counts/new deployment ID;
- no signing, production namespace, scheduler, provider, or Paper-v2 effects;
- exact review before advancing.

## R2 — signing boundary

- sign only the exact reviewed canonical attestation;
- verify detached signature and public digest;
- signing is separately authorized and does not authorize deployment;
- rebuild/change after signing invalidates the reviewed material.

## R3 — read-only halted-host preflight

Prove twice-stable:

- exact S5-R10 canonical deployment;
- exact old final lease and old activation/end/soak;
- exact disabled/non-running D10 scheduler;
- historical S5-R8 retired root absent, matching accepted P125-R1I cleanup;
- new retired destination absent;
- new Architecture-128 staging destination absent;
- no conflicting reserved names;
- provider/Paper-v2/broker/live not run.

No mutation.

The exact new staging tree is not a prerequisite of R3 because R3 is the
pre-mutation checkpoint. R4 authorization covers staging construction. After
staging is constructed and independently verified, R4 must run a fresh full
read-only admission that additionally proves the exact staging identity before
either rename.

## R4 — protected deployment replacement

Separate explicit authorization required.

Expected mutation budget:

```text
rename #1:
D10 -> D10.retired-9f3d111b-25bb-5ee4-9abf-f5215a32b826

rename #2:
D10.replacement-<new-deployment-id>.installing -> D10
```

Rules:

- no replace;
- scheduler stays disabled;
- fresh read-only classification after each native call;
- no retry/rollback/delete/cleanup;
- ambiguity stops;
- PASS leaves new canonical deployment inert with lease absent and evidence root
  present.

## R5 — Trading read-only qualification

Under actual non-admin Trading:

- verify signed deployment/source/guard/runtime;
- verify evidence root;
- require activation lease absent;
- require no current-soak evidence file yet;
- trap second-stage launch;
- no scheduler/provider/Paper-v2/broker/live effect.

## R6 — source-only reactivation operator

Implement/freeze:

- new activation/expiry/soak derivation with old soak reuse rejected;
- fixed lease-derived evidence filename;
- create-only empty evidence-file provisioning;
- exact Architecture-127 ACL/capability verification;
- append-only WRITE_THROUGH open-without-write probe;
- scheduler update/readback while lease absent;
- existing lease tmp/installing/final publication protocol;
- final lease as arming action;
- post-arm exact observer/readback;
- reconciliation-only handling for ambiguity;
- no manual start.

Focused tests must cover every ordering edge before broad certification is
considered.

## R7 — protected new activation

Separate explicit authorization required.

Protected order:

1. fresh read-only admission;
2. freeze exact new activation/end/soak;
3. create and verify empty lease-derived evidence file;
4. fresh admission after any credential pause;
5. update exact disabled task to new bounded D10 schedule;
6. independent COM readback;
7. reverify deployment/evidence/lease absence;
8. publish exact lease tmp -> installing -> final;
9. final independent deployment/scheduler/lease/evidence reread.

Any ambiguity stops. No automatic retry or rollback.

## R8 — first natural wake

- no manual task start;
- wait for the first natural scheduled wake;
- observe exact current-soak durable evidence through Architecture 127;
- require valid WAKE_START and matching terminal/result/ACCEPT grammar;
- reconcile scheduler plus durable trading state independently;
- accept D10-C only if the complete reviewed evidence contract passes;
- otherwise halt and do not auto-restart.

## Source regression requirements

At minimum test:

1. old deployment/lease/soak identities cannot be caller-selected;
2. old soak ID cannot be reused;
3. new retired/staging paths are deterministic and fixed;
4. replacement requires disabled/non-running task;
5. rename order fixed; no replace;
6. interrupted OLD_RETIRED and NEW_CANONICAL states require reconciliation;
7. new deployment requires Architecture-127 evidence root;
8. activation prohibited while new final lease already exists;
9. evidence filename only from verified new lease;
10. evidence file must start empty and exact-policy;
11. evidence file grants append-only but not FILE_WRITE_DATA/delete/security
    mutation;
12. no evidence append is performed during provisioning;
13. scheduler mutation precedes final lease;
14. final lease publication is impossible after scheduler mismatch;
15. final lease publication is impossible after evidence-file drift/nonempty
    state;
16. partial evidence/lease/scheduler mutation produces reconciliation-required
    classification, never retry authority;
17. scheduler action stays the exact sealed guard with zero semantic arguments;
18. manual task start absent;
19. first natural wake uses exact Architecture-127 observer;
20. provider/Paper-v2/broker/live remain closed throughout R1-R7 plumbing.

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

### Architecture 128 R3 runtime-scope clarification

R3 does not require a fresh Trading-process/runtime qualification. R4 mutates
only the inert D10 deployment namespace and does not execute D10 or modify the
protected runtime. R3 therefore proves the protected parent plus exact halted
D10 signed deployment, lease, disabled scheduler, and fixed absence namespaces.
R5 retains the mandatory fresh non-admin Trading/runtime qualification of the
new canonical deployment before any reactivation work can proceed.

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

