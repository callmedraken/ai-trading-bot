# Architecture 124 — D10 Sealed Pre-Source Launch Guard Validation Plan

Status: frozen source/deployment plan. No production provisioning, scheduler
mutation, activation, or trading effect is authorized.

## A. Source checkpoints

### A124-1 — launch-contract and attestation revision

Revise source-owned D10 deployment constants so that:

- Task Scheduler targets the fixed installed launch guard, not a source-tree
  trading launcher;
- the exact guard invocation is
  `python.exe -I -S -B -X pycache_prefix=F:\AITradingBot\D10\no-pycache
  F:\AITradingBot\D10\launch-guard.py`;
- the sealed deployed source root is `F:\AITradingBot\D10\source`;
- the attestation additionally binds exact launch-guard byte length and SHA-256;
- the A2 certification builder includes the tracked launch-guard source bytes
  in the attestation while the executable manifest continues to describe the
  sealed second-stage source snapshot.

This checkpoint is pure/source-only.

### A124-2 — fixed D10 security/native contracts

Implement fixed D10 paths, exact Administrator/SYSTEM/Trading read-only policy,
reserved temporary names, and mocked/native-safe no-follow inspection
interfaces for:

- D10 root;
- launch guard;
- attestation;
- signature;
- executable manifest;
- sealed source root and governed snapshot.

Do not widen Architecture-77 fixed paths.

### A124-3 — pre-source guard

Implement one self-contained guard source artifact.

Before source verification it may import only builtin/standard-library modules
from the fixed protected production Python runtime. It must never import
`trading_bot` or the deployed source tree.

The guard performs fixed-path/token/security checks, signed-attestation
verification, complete deployed-manifest verification, alternate-bytecode/cache
rejection, and final drift checks.

On success only, it launches exactly one fixed second-stage D10 Python command.
On failure it launches nothing.

Use pure/mock seams for portable testing. No production root is touched.

### A124-4 — production Python substrate qualification contract

Define the exact read-only acceptance evidence required to prove
`F:\AITradingBot\runtime` is Administrator/SYSTEM controlled and not writable
or replaceable by Trading for the duration of D10.

This may require a dedicated protected operator/native acceptance phase. Do not
silently assume the runtime installation is sealed.

### A124-5 — Architecture-123 A4 integration

After the guard boundary is accepted, implement the governed-source A4
deployment re-verifier as defense in depth.

A4 is not the bootstrap trust root and cannot substitute for the guard.

### A124-6 — Architecture-122 activation lease

Resume the one-week activation lease only after A124-1 through A124-5 are
accepted.

The final guard checks ACTIVE lease status before it launches the governed D10
source.

## B. Focused test requirements

Before broad certification, focused tests must prove:

- scheduler no longer launches the mutable development worktree;
- exact guard and second-stage command lines;
- `-I`, `-S`, `-B`, and fixed `pycache_prefix`;
- no semantic CLI arguments;
- fixed absent cache-prefix target;
- guard digest/length attestation binding;
- sealed source root canonicalization;
- no `.git` runtime authority;
- no project import before guard verification;
- rejected trust/signature/manifest/source/cache state launches no child;
- extra `__pycache__`, `.pyc`, or `.pyo` blocks;
- exact manifest success launches one fixed child only;
- environment cannot select source/path/authority;
- protected source/guard policies deny Trading mutation;
- current Architecture-123 A1/A2 regressions remain green;
- current Architecture-122/111/114/121 regressions remain unchanged where
  contracts overlap.

Use focused tests plus Ruff/format/diff checks during implementation. Do not run
the broad certification runner until the final D10 source tree is frozen.

## C. Protected host/deployment checkpoints

No source checkpoint authorizes these operations.

### P124-1 — production Python substrate qualification

Under the appropriate administrator/Trading perspectives, prove the fixed
production runtime installation satisfies the frozen pre-source trust policy.

### P124-2 — sealed D10 source/guard provisioning

Administrator creates the fixed D10 root/source snapshot, installs exact
certified guard/source bytes, applies reviewed protected ACLs, and verifies the
complete final inventory.

### P124-3 — signing and trust publication

Externally sign the exact canonical deployment attestation and atomically
publish attestation/signature/manifest through the reviewed create-only
publication path.

### P124-4 — Trading guard qualification

Under non-admin Trading, invoke the guard in explicit no-effect qualification
mode or equivalent read-only acceptance harness. It must prove the signed
deployment and launch no trading source/effect.

### P124-5 — activation lease and scheduler mutation

Only after separate operator approval may the exact one-week activation lease
be provisioned and the capture-only task changed to the fixed launch guard.

## D. Stop conditions

STOP rather than weaken the contract if:

- production Python runtime cannot be proven protected from Trading writes;
- the guard requires importing project/source-tree code before verification;
- Python startup can execute mutable non-runtime/site content before the guard;
- source snapshot cannot be made immutable to Trading;
- signed attestation cannot bind the exact guard and source deployment;
- any verification failure could still reach second-stage source execution.


## Second-stage dependency bootstrap requirement

Before A124-3 is accepted, tests must prove that the verified second-stage
launcher can run under `-I -S -B` without relying on automatic `site`
initialization.

The launcher must explicitly add only:
- the sealed `source\src` path;
- the fixed protected production-runtime site-packages path.

It must not invoke `site.main()` or execute `.pth`/sitecustomize/
usercustomize startup hooks.

A124-4 host qualification must prove the fixed runtime package directory is
Administrator/SYSTEM controlled and non-writable by Trading.
