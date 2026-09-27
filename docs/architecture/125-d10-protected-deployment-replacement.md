# Architecture 125 — Inactive D10 Protected Deployment Replacement

Status: frozen design-only checkpoint for replacing the historical inactive S5-R8 D10 deployment with the accepted S5-R10 deployment material. This document authorizes no Administrator mutation, signing, scheduler change, activation lease, provider effect, paper effect, broker-paper effect, or live-trading effect.

## 1. Scope

Architecture 125 defines exactly one replacement lineage:

- old protected deployment: accepted historical S5-R8 D10 deployment;
- new deployment material: accepted S5-R10 unsigned deployment material;
- canonical protected root: F:\AITradingBot\D10;
- outer protected parent: F:\AITradingBot.

It exists because the Architecture-124 P124-2 operator is intentionally create-only and requires the canonical D10 root to be absent. P124-2 remains the correct primitive for an absent-root initial deployment. It is not an in-place upgrade primitive and must not be widened into one.

This replacement contract is not a generic deployment upgrader. A later source upgrade must freeze a new replacement lineage or explicitly generalize this architecture under separate review.

## 2. Frozen old and new identities

The replacement operator must source-own and verify the exact identities below. They are never caller-selected arguments.

Historical S5-R8 protected deployment:

    deployment ID:
    2fd79986-fb50-5fe4-800a-2d4aa5e7307c

    executable manifest SHA-256:
    e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a

    executable file count:
    306

    executable total bytes:
    5391245

    launch guard byte length:
    68411

    launch guard SHA-256:
    3b28d0ffeede06a4785a903dbf6a48c12204651ce8a3c2f80cd6a1428efd8d1a

    unsigned attestation SHA-256:
    a12ab7788120934ca928919a01b4cfc7a3f6f307fad79ab13a6bfff189aeb3f3

    accepted detached signature SHA-256:
    7ae83e28bcd8ab7cb59ab990a7f3b3191f485621aa83f5431f7f25fc32c8b4eb

Accepted S5-R10 replacement material:

    certified source HEAD:
    c5cc0b01301600daf17f1114f4451dca2c9d7a1f

    certified source TREE:
    bfacfadaa14315d2d378abcc0f1e4bc7c42034f1

    operator/pin HEAD:
    19c585519daefad917d6326b5180177b63f8e7f0

    operator/pin TREE:
    ab0dccdea1e0e6646ba3b68b3afb725a553f68cc

    deployment ID:
    9f3d111b-25bb-5ee4-9abf-f5215a32b826

    executable manifest SHA-256:
    e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a

    executable file count:
    306

    executable total bytes:
    5391245

    launch guard byte length:
    69259

    launch guard SHA-256:
    37d78c65800a315a12049b6c278addf609589d121e15d31dd9064dc8ec427298

    unsigned attestation SHA-256:
    4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2

The unchanged manifest digest and executable byte count are expected: the corrected launch guard is attested separately from the 306-entry sealed-source manifest.

## 3. Authority precondition: D10 must be inactive

Replacement is permitted only while all D10 recurring/effect authority is closed.

Before any protected namespace mutation, the operator must independently prove:

1. the process is an elevated Administrator under the existing native proof;
2. F:\AITradingBot has the exact accepted protected two-ACE parent policy;
3. the canonical F:\AITradingBot\D10 tree is the exact accepted S5-R8 deployment, including native path identity, owner/DACL policy, no reparse, complete governed source inventory, trust bytes, signature validity, guard bytes, and deployment identity;
4. activation.lease.json, activation.lease.json.installing, activation.lease.json.tmp, and no-pycache are absent;
5. every replacement temporary/quarantine name defined by this architecture is absent;
6. the Task Scheduler task at \AITradingBot-PD4-UnattendedPaper-v1 is still the exact accepted capture-only D5 predecessor and is not the D10 guard action;
   this proof must use the Architecture-126 COM-first read-only observation contract; raw XML hash equality is not scheduler authority;
7. no source-owned observation indicates D10 P124-5 activation or scheduler mutation ever completed.

An absent, unreadable, conflicting, partially activated, or indeterminate condition blocks before the first mutation.

The scheduler proof is part of replacement admission even though Task Scheduler is not trading authority. It prevents replacing executable bytes while a D10 wake source could legitimately target the canonical D10 root.

## 4. Fixed replacement namespace

The replacement implementation must use source-owned fixed names derived from the two frozen deployment IDs. Paths are not accepted from CLI, environment variables, configuration files, or stdin.

New staging root:

    F:\AITradingBot\D10.replacement-9f3d111b-25bb-5ee4-9abf-f5215a32b826.installing

Historical quarantine root:

    F:\AITradingBot\D10.retired-2fd79986-fb50-5fe4-800a-2d4aa5e7307c

Canonical root:

    F:\AITradingBot\D10

All three roots must be on the same local NTFS volume and below the exact protected F:\AITradingBot parent. The staging and retired roots use the same Administrator-owned protected three-ACE D10 object policy as the canonical D10 root.

The implementation must use no replace-existing rename flag. Every namespace transition is create-only or destination-absent.

## 5. Staging the S5-R10 deployment

Before touching the old canonical root, the operator constructs the complete new inert P124-2-equivalent payload under the fixed staging root.

The staging payload contains only:

- S5-R10 launch-guard.py;
- S5-R10 sealed source snapshot;
- no trust files;
- no activation lease;
- no cache prefix;
- no scheduler state.

The existing certified-material builder remains the source of new bytes. The replacement code may reuse the reviewed P124-2 layout and native ACL/write primitives only after their path allowlists are explicitly extended for the fixed staging namespace.

Before the old root is renamed, the operator must independently reopen and verify the entire staging tree:

- exact expected directories and files;
- exact S5-R10 bytes;
- exact file counts and byte lengths;
- exact owner and protected DACL;
- local NTFS, non-reparse, single-link regular files/directories;
- no extra, missing, case-colliding, .git, __pycache__, .pyc, .pyo, lease, trust, or cache object;
- stable native identity before and after every bounded read.

A staging verification failure leaves the historical S5-R8 canonical root untouched.

## 6. Final pre-swap revalidation

Immediately before the first rename, the operator re-proves all replacement admission facts rather than relying on earlier process-local results:

- exact S5-R8 canonical deployment;
- exact S5-R10 staging deployment;
- exact parent policy;
- absent activation/cache/reserved objects;
- exact D5 scheduler predecessor;
- fixed same-volume namespace.

Any drift blocks with both roots left in their then-current state. No cleanup rename is attempted automatically after an admission failure.

## 7. Two-step same-volume publication

After final revalidation, the only allowed namespace mutation sequence is:

    step A:
    F:\AITradingBot\D10
      -> F:\AITradingBot\D10.retired-2fd79986-fb50-5fe4-800a-2d4aa5e7307c

    step B:
    F:\AITradingBot\D10.replacement-9f3d111b-25bb-5ee4-9abf-f5215a32b826.installing
      -> F:\AITradingBot\D10

Both are same-volume MoveFileW-style renames with destination absence required and no overwrite semantics.

There is intentionally no attempt to make the two renames transactionally atomic as a pair. Safety comes from the fact that every intermediate namespace state is non-authoritative:

- before step A, the old S5-R8 D10 is canonical but inactive;
- after step A and before step B, the canonical D10 root is absent;
- after step B, S5-R10 guard/source is canonical but has no signed trust and no activation lease.

Therefore a crash at every publication window fails closed rather than leaving an executable deployment with effect authority.

## 8. No automatic recovery from an indeterminate rename

A native API success result may advance the in-process state machine. An exception, process crash, unavailable result, or ambiguous post-call observation never authorizes retrying either rename optimistically.

On any interrupted or indeterminate replacement, a later invocation performs read-only namespace classification first. It must classify exactly one of these states:

- OLD_CANONICAL: exact old D10 canonical, exact new staging present, retired absent;
- OLD_RETIRED: canonical absent, exact old retired, exact new staging present;
- NEW_CANONICAL: exact new D10 canonical, exact old retired, staging absent;
- CLEAN_INITIAL: exact old D10 canonical, staging absent, retired absent;
- CONFLICTING: anything else.

The ordinary replacement command does not automatically continue from OLD_RETIRED or NEW_CANONICAL after a prior interrupted invocation. Those states require a separate explicit recovery decision and reviewed recovery command. CONFLICTING always blocks.

This preserves the project rule that ambiguous external/protected effects are not converted into retry authority.

## 9. Post-publication verification

If both renames return success in the same admitted invocation, the operator must immediately verify:

1. canonical F:\AITradingBot\D10 is exactly the S5-R10 guard/source-only deployment;
2. the staging root is absent;
3. the retired root is exactly the historical S5-R8 deployment and remains protected;
4. canonical trust files are absent;
5. canonical activation/cache/reserved objects are absent;
6. the D5 scheduler predecessor remains unchanged;
7. the F:\AITradingBot parent policy remains exact.

A verification failure returns BLOCKED and does not roll the old deployment back into the canonical path.

Automatic rollback is forbidden. Restoring historical S5-R8 trust to the canonical path after S5-R10 publication would create a new authority transition and must never be an error-cleanup side effect.

## 10. Relationship to P124-3 and retirement cleanup

A successful Architecture-125 replacement leaves:

- canonical D10: exact S5-R10 guard/source, unsigned and inactive;
- retired path: exact historical S5-R8 deployment/trust, non-canonical and inactive;
- scheduler: exact D5 capture-only predecessor;
- activation lease: absent.

The next protected operation is the existing P124-3 signing/trust publication against canonical S5-R10.

The historical retired tree is deliberately not deleted by the replacement operation. Destruction of historical accepted trust/source is a separate protected cleanup checkpoint.

After P124-3 PASS, a P125 retirement-cleanup operation may be considered. It must first prove:

- canonical S5-R10 signed trust verifies exactly;
- canonical activation lease/cache remains absent;
- scheduler remains the D5 predecessor;
- retired tree is exactly the frozen S5-R8 deployment;
- no other object exists under the retired namespace.

Only then may a fixed-path, native no-follow, manifest-bound bottom-up deletion of the retired S5-R8 tree occur. Partial cleanup never affects canonical S5-R10 and is recoverable only by exact read-only reclassification.

P124-1 full signed production-Python substrate qualification occurs only after the retired-tree cleanup PASS, so its protected-host inventory does not need to admit an obsolete sibling deployment.

## 11. Protected execution sequence after this design

The revised protected sequence is:

    P125-R1 source implementation and focused verification
    -> source review/certification gate
    -> separately authorized P125 protected replacement
    -> P124-3 new S5-R10 signing/trust publication
    -> separately authorized P125 retired-S5-R8 cleanup
    -> full signed-trust P124-1
    -> P124-4 Trading guard qualification
    -> P124-5 activation lease + scheduler mutation only after separate approval

No step inherits authorization from the previous step merely because the previous step passed.

## 12. Implementation boundaries

Expected source implementation is separated into pure contract/state logic and native Windows mutation adapters.

The source implementation should add dedicated Architecture-125 modules rather than weakening the create-only P124-2 functions.

Recommended shape:

- scripts/d10_protected_replacement.py
  - frozen identities and paths;
  - replacement namespace classifier;
  - pure admission/state-machine validation;
  - deterministic transcripts;
- scripts/d10_protected_replacement_windows.py
  - fixed-path no-follow Windows inspection;
  - exact D5 scheduler read-only qualification;
  - same-volume create-only staging and rename primitives;
  - no generic arbitrary-path rename/delete API;
- scripts/p125_replace_d10.py
  - explicit Administrator replacement entry point;
- scripts/p125_retire_old_d10.py
  - separate explicit retirement cleanup entry point.

Substantial operator orchestration must be in reviewed .py/.ps1 files. Interactive PowerShell remains a short launcher/check wrapper. Structured data uses files or stdin rather than JSON argv. Native stdout/stderr and exit status are handled explicitly. The canonical local operator/helper-script folder is F:\Users\John\Downloads.

## 13. Transcript and evidence requirements

Replacement and cleanup emit bounded canonical transcripts with no secrets, handles, reusable authority, raw ACL blobs, or caller-selected paths.

Replacement PASS evidence includes:

- old and new deployment IDs;
- old/new guard SHA-256;
- manifest digest/file count/total bytes;
- admitted scheduler disposition;
- activation-lease disposition;
- fixed staging/retired/canonical paths;
- each completed rename step;
- post-publication canonical verification;
- retired-tree verification;
- activation_authority = NONE;
- scheduler_authority = NONE;
- trading_authority = NONE.

A BLOCKED transcript contains a closed reason code and the highest definitely completed namespace state. It must not claim a rename failed if the result was indeterminate.

## 14. Required tests before any protected replacement consideration

Source acceptance requires focused tests for at least:

1. exact old/new identity constants;
2. fixed path allowlists and rejection of caller-selected paths;
3. exact D5 scheduler predecessor required before mutation;
4. activation/lease/cache/trust staging conflicts block;
5. wrong or drifted S5-R8 canonical deployment blocks;
6. wrong or drifted S5-R10 staging deployment blocks;
7. staging completes and verifies before old-root mutation;
8. no replace-existing rename semantics;
9. rename ordering is old-to-retired before staging-to-canonical;
10. crash/state classification for every publication window;
11. no automatic retry/recovery after indeterminate mutation;
12. post-publication new canonical identity and old retired identity;
13. no automatic rollback;
14. P124-3 remains the only signing/trust publication step;
15. replacement never writes activation lease/cache or Task Scheduler;
16. retirement cleanup is impossible before exact S5-R10 signed trust;
17. retirement cleanup cannot touch canonical D10;
18. partial retirement cleanup remains fail-closed;
19. transcripts remain sanitized and deterministic;
20. no provider, settlement, decision-publication, receipt-recovery, broker-paper, or live effect.

Focused tests and Ruff/diff checks precede broad certification. Final repository certification continues to use scripts/run_test_certification.py with the reviewed three-lane topology, not bare pytest.

## 15. Exit condition

Architecture 125 is complete when the design above is source-frozen and the canonical project status/handoff documents point to P125-R1 source implementation as the next checkpoint.

This architecture alone does not authorize creation of staging/retired paths, rename of F:\AITradingBot\D10, deletion of the retired tree, signing, P124-1/P124-4/P124-5, or any trading effect.
