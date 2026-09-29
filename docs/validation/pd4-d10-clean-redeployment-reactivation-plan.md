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
- exact historical S5-R8 retired root;
- new retired destination absent;
- exact new staging tree present and verified;
- no conflicting reserved names;
- provider/Paper-v2/broker/live not run.

No mutation.

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

