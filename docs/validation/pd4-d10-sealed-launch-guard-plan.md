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

## A124-4 frozen production-Python substrate acceptance

A124-4 is a source-only, read-only acceptance model in
src/trading_bot/runtime/personal_desktop_d10_python_substrate.py. It never
opens the production runtime. Its typed QualificationEvidence is input to a
later protected P124-1 native collector; a caller-built instance is not
authority. QualificationResult contains fixed paths, version, accepted search
roots and a count, with no handle, raw ACL, token, or reusable capability.
P124-1 must retain a native transcript for operator review. The transcript
schema is v4 and records the explicit volume-namespace or protected-object
access policy for each effective-access row, the distinct loader-reported and
handle-derived path spellings for dynamic module and DLL observations, and the
native link count for each System32 DLL. This result does not authorize a D10
launch.

The source-owned identity is exactly F:\AITradingBot\runtime\python.exe,
Python 3.14.3, runtime F:\AITradingBot\runtime, and package path
F:\AITradingBot\runtime\Lib\site-packages. The package path was measured under
-I -S and is path identity only until P124-1 proves it protected. A different
interpreter, version, runtime prefix, drive, or package directory requires
architecture review and a newly signed Architecture-123 attestation. The
P124-1 signed-attestation input must match this exact path and version.

Fixed governed paths retain exact native final-path semantics, including
F:\, F:\AITradingBot, F:\AITradingBot\runtime, the fixed production
python.exe, the fixed C:\Windows\System32 parent, and fixed signed D10
inputs. Dynamic Python module origins and GetModuleFileNameExW runtime and
direct System32 DLL paths are syntax-checked against their frozen namespace,
opened by the existing native no-follow path, and compared with the native
final path from that handle. Reported spelling may differ from native final
spelling only by Windows filename case; equality is normalized and
case-insensitive, and any directory, basename, volume, or other non-case
difference blocks. The actual native final spelling is retained separately in
the transcript. Runtime final paths must map case-insensitively to exactly one
protected runtime inventory file. The complete runtime inventory's
case-collision rejection and exactly-one-link requirement for runtime files
remain mandatory. Windows System32/KnownDLL DLLs may legitimately have
multiple NTFS hard links. Their positive native link count is observed and
retained in the transcript; a count greater than one alone is not a blocker.
An invalid, zero, negative, unavailable, or indeterminate System32 link count
blocks, and same-handle re-observation must detect link-count drift. The
System32 parent remains an exact fixed path; direct-child-only .dll,
non-reparse file identity, owner/DACL, actual Trading mutation and file-delete
denial, parent mutation and FILE_DELETE_CHILD replacement denial, no-follow
opening, and all other drift checks remain mandatory.

P124-1 must collect and preserve these observations:

1. Under Administrator, open F:\, F:\AITradingBot, and every object in the
   entire F:\AITradingBot\runtime subtree by native no-follow handles. Pin
   parents and children, reject reparse points throughout and hard-linked
   files within the governed runtime subtree (each runtime file must have
   exactly one link), inspect
   GetFinalPathNameByHandleW, object kind, file ID, volume serial, fixed local
   NTFS volume, owner SID, DACL-protected control bit, and complete ACE
   type/order/flags/masks. Enumerate every directory's direct names, reject
   case collisions, require an exact parent-child inventory, and re-inspect
   pinned identities before closing. Any inaccessible, unknown, redirecting,
   or changed object blocks acceptance. The F:\ volume parent is included
   because Trading must not be able to rename/replace the
   F:\AITradingBot child through it. Its exact local-NTFS volume/final-path
   identity, complete/stable ACL and owner observation, and the child's
   presence/identity are required. Its existing DACL need not match the
   three-ACE runtime policy or be protected. F:\AITradingBot is the already
   accepted protected deployment parent: exact Administrators owner, protected
   DACL, and exactly
   two ordered allow ACEs (Administrators then SYSTEM, flags 0, each mask
   0x001F01FF). It has no Trading ACE. F:\AITradingBot\runtime is the
   protected inheritance trust anchor: it is a directory owned by
   Administrators or SYSTEM, with exactly three explicit ALLOW ACEs ordered
   SYSTEM, Administrators, Trading. Their masks are respectively 0x001F01FF,
   0x001F01FF, and 0x001200A9, and every ACE has flags exactly 0x03
   (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE). Every directory strictly
   below it has an unprotected DACL with only those ordered inherited ACEs
   and masks, each with flags exactly 0x13 (OI | CI | INHERITED_ACE). Every
   file strictly below it has an unprotected DACL with only those ordered
   inherited ACEs and masks, each with flags exactly 0x10 (INHERITED_ACE).
   No explicit, extra, deny, inherit-only, no-propagate, or other ACE/flag is
   accepted. This covers Lib, DLLs if present, python314.zip if present,
   site-packages, stdlib, extension modules, and DLLs. Trading receives only
   read/execute or read/traverse, never mutation authority.

   Unprotected descendants are accepted only through exhaustive no-follow
   enumeration and pinned ancestry to the protected runtime root, exact parent
   file-index linkage, case-collision rejection, same-handle identity and
   security re-observation, and before/after inventory equality. The exact
   inherited ACEs permit no explicit addition. Actual Trading mutation and
   replacement denial is independently proven for each object and parent.
2. Prove effective rights under the actual non-admin local Trading token/SID
   for every admitted object and its parents. Use an explicit volume-parent
   namespace policy for F:\: actual Trading FILE_DELETE_CHILD, WRITE_DAC,
   and WRITE_OWNER must all be denied. A grant of unrelated volume-root
   add-file/add-subdirectory, write-metadata, or DELETE on the volume-root
   object itself does not fail that policy. For F:\AITradingBot and every
   runtime object, retain the strict full MUTATION_MASK
   zero-grant policy: Trading must lack file and directory write/append,
   add-file/add-subdirectory, delete, delete-child, rename/replace,
   WRITE_DAC, WRITE_OWNER, and any equivalent generic or inherited right.
   Deleting/renaming F:\AITradingBot requires DELETE on that child or
   FILE_DELETE_CHILD on F:\; both must be denied. The read-only access
   check must include the token's
   enabled groups and privileges; a simple Trading ACE scan is insufficient.
   The actual exact-SID, non-admin, non-elevated Trading token must have
   SeChangeNotifyPrivilege enabled for bypass-traverse access to fixed permitted
   descendants. Administrators group membership and the existing dangerous
   bypass/mutation privileges remain disallowed. Bypass traverse grants neither
   parent listing nor protected-object mutation. A mismatched token or
   indeterminate access check blocks. ACL/owner checks and Trading access
   checks must agree for both policies, including complete group/privilege
   accounting and stable ACL re-read. The native transcript must explicitly
   establish F:\AITradingBot child replacement denial through the volume
   parent's FILE_DELETE_CHILD check, plus DELETE and parent
   FILE_DELETE_CHILD/replace denial for the root and every admitted
   protected object; an untested operation is not a denial.
   Administrator or SYSTEM may maintain
   the installation only outside an active D10 interval.
3. Use native no-follow absence probes to prove parent/runtime pyvenv.cfg and
   runtime python._pth, python3._pth, python314._pth absent. Complete runtime
   enumeration must reject every other ._pth or pyvenv.cfg anywhere under
   runtime. If an equivalent path-configuration mechanism exists, stop for
   architecture review. For each of python314.zip and DLLs, exactly one
   native state is required: protected-present in the complete inventory XOR
   proven-absent by a no-follow probe. Both or neither block, whether or not
   the path appears in sys.path. Every sys.path candidate must match its exact
   proven state. A nonexistent zip path in sys.path is not itself a security
   proof.
4. Invoke only the fixed executable with exact guard startup switches
   -I -S -B -X pycache_prefix=F:\AITradingBot\D10\no-pycache in a read-only
   diagnostic that does not import the D10 guard or trading source. Capture
   exact sys.executable, prefix, base_prefix, version, sys.flags,
   pycache_prefix, ordered sys.path, sysconfig purelib and platlib, and
   origins/final paths of every builtin, frozen, stdlib, extension and
   guard-import dependency under that startup behavior. The only admitted
   filesystem import/search roots are fixed runtime root, Lib, DLLs, and
   python314.zip; each actual root must appear in protected native inventory,
   and each missing candidate needs exact absence proof. The current
   directory, user site, environment path, sealed source, package directory,
   and alternate installation may not appear before the guard. Actual guard
   extension/DLL loads must resolve to protected runtime objects. Windows
   OS/KnownDLL loads are a separate P124-1 transcript: the fixed System32
   parent identity remains exact, while a dynamically reported direct-child
   DLL path may differ from its handle-derived final path only by Windows
   filename case. Keep reported and native final spellings separately, with
   OS directory provenance, protected owner/DACL, and Trading effective denial
   independently reviewed. Only DLLs directly beneath the fixed
   C:\Windows\System32 directory are admissible; a different Windows
   installation path or unknown OS DLL redirection blocks. P124-1 must attest
   completeness of the Windows/KnownDLL transcript and of the runtime/import
   dependency observation, including builtin/frozen and guard-import coverage.
   Empty or incomplete loaded-DLL or runtime-file collections block; a
   collector returning no rows is not proof that no dependency existed.
5. Re-observe runtime/security facts after the diagnostic, including directory
   inventories and configuration absence. Signed A123 Python path/version,
   source-owned constants, native transcript, and Trading token proof must
   agree. Any mismatch or collection error is a STOP.

The later verified launcher may append only exact qualified site-packages after
sealed-source verification. Qualification does not call site.main(), execute
.pth, or run site customization; -S remains set. A124-4 performs no D10 root
provisioning, signing, lease, scheduler, provider, publication, settlement,
broker-paper, or live operation and does not extend Architecture-77 fixed
authority objects. P124-1 is a separate protected host checkpoint; D10 remains
blocked until its native evidence is accepted.

## P124 protected execution dependency

The source-only P124-1 collector accepted after S5 verifies a real detached-signed Architecture-123 attestation from the fixed D10 trust root. Therefore P124-1 cannot execute before those fixed trust objects exist.

For the protected operator phase, retain the checkpoint labels but use this dependency order:

1. **P124-2** — provision the sealed guard/source snapshot and reviewed protected D10 namespace; no execution or scheduler mutation.
2. **P124-3** — externally sign the exact certified attestation and publish the attestation/signature/manifest through the reviewed create-only path; no activation or scheduler mutation.
3. **P124-1** — run the reviewed Administrator/Trading native substrate collector against the fixed production runtime and the now-existing signed attestation; require PASS and retain its transcript.
4. **P124-4** — under non-admin Trading, perform the no-effect guard qualification against the signed deployment.
5. **P124-5** — only after separate approval and all prior acceptance evidence, publish the activation lease and mutate the capture-only scheduler to the fixed guard.

This ordering does not weaken the production-Python prerequisite: P124-1 still must PASS before any guard qualification, activation lease, scheduler mutation, or D10 effect. P124-2/P124-3 artifacts are inert if P124-1 later blocks.
