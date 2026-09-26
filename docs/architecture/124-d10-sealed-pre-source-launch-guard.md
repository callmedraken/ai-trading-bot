# Architecture 124 — D10 Sealed Pre-Source Launch Guard

Status: frozen prerequisite for Architecture 123 A3/A4 and Architecture 122 D10.
This document authorizes no provisioning, scheduler mutation, activation, or
trading effect.

## 1. Problem

The Architecture-123 A3 implementation correctly stopped before source changes.

The frozen D10 scheduler target launched the source-tree D10 script directly
through Python. Python necessarily executes that top-level script and imports
runtime modules before an in-process deployment verifier can establish that
those source bytes are the certified deployment. Isolated mode does not remove
that circularity, and imported modules may also select cached bytecode.

An in-source verifier therefore cannot be the first authority boundary.

## 2. Trusted launch substrate

D10 introduces one sealed pre-source launch guard installed outside the
governed trading source tree:

```text
F:\AITradingBot\D10\launch-guard.py
```

Task Scheduler invokes only this fixed installed guard through the fixed
production interpreter.

The guard is an Administrator-owned, protected-DACL, non-reparse regular file.
Trading has read/execute-required access but no create/write/delete/rename,
WRITE_DAC, or WRITE_OWNER authority in the D10 root.

The pre-existing `F:\AITradingBot` deployment parent retains the accepted
Architecture-78/103/PD1 policy: Administrators owner, protected DACL, exactly
ordered Administrators and SYSTEM allow ACEs with flags 0 and full-control
mask 0x001F01FF, and no Trading ACE. Architecture-124's three-ACE
Trading-readable policy begins at `F:\AITradingBot\D10`, including its guard,
source descendants, and trust files; it does not apply to the outer parent.
Trading reaches exact permitted descendants through its qualified enabled
SeChangeNotifyPrivilege (Windows bypass traverse), without parent listing or
mutation rights on protected objects. P124-1 applies two distinct effective-access
policies. The volume parent `F:\` retains its exact native local-NTFS,
no-follow/final-path identity, complete and stable ACL/owner observation, and
the `F:\AITradingBot` child identity. The actual Trading token must lack
FILE_DELETE_CHILD, WRITE_DAC, and WRITE_OWNER on `F:\`. Other volume-root
create, metadata-write, or DELETE-on-the-volume-object rights do not establish
authority to delete, rename, or replace `F:\AITradingBot`: Windows requires
DELETE on that child or FILE_DELETE_CHILD on its parent for child
deletion/rename. `F:\AITradingBot` and every protected runtime descendant
retain full zero-grant MUTATION_MASK, DELETE and parent FILE_DELETE_CHILD/
replacement denial, WRITE_DAC/WRITE_OWNER denial, and their exact ACL/owner
policies. Complete token-group/privilege accounting and ACL re-read agreement
remain mandatory for both policies. No parent ACL migration is required or
authorized.

The guard is installed from the exact certified repository guard bytes during a
later protected administrator deployment checkpoint. Its byte length and
SHA-256 digest are bound into the signed Architecture-123 deployment
attestation.

The guard is executed as the top-level Python script; it is not imported from
the trading source tree.

## 3. Sealed deployed source snapshot

D10 no longer executes recurring authority from a mutable Git worktree.

The exact certified executable deployment is copied into:

```text
F:\AITradingBot\D10\source\
  src\trading_bot\...
  scripts\run_personal_desktop_unattended_one_week_soak.py
```

There is no `.git` authority in this snapshot.

The source snapshot is Administrator-owned, protected-DACL, local NTFS,
non-reparse, and read-only to Trading. Trading cannot create, replace, rename,
delete, or change ACL/ownership of governed files or directories.

The signed Architecture-123 executable manifest describes exactly this deployed
snapshot. Extra governed files are prohibited.

The Architecture-123 attestation source root is therefore revised from the
development worktree to:

```text
F:\AITradingBot\D10\source
```

## 4. Python startup contract

The scheduler launches the guard with the exact fixed argument shape:

```text
F:\AITradingBot\runtime\python.exe
  -I
  -S
  -B
  -X
  pycache_prefix=F:\AITradingBot\D10\no-pycache
  F:\AITradingBot\D10\launch-guard.py
```

The argument vector carries no market/trading semantics.

`-I` isolates the interpreter from user-site and Python environment inputs.
`-S` prevents automatic `site` initialization and `.pth`/site customization
before the guard.
`-B` prevents bytecode-cache writes.
The fixed `pycache_prefix` moves cache lookup away from the deployed source
tree. The `no-pycache` target must remain absent under the Administrator-owned
D10 root, so source-tree `__pycache__` files are not selected and no alternate
cache can be created by Trading.

The source snapshot itself must contain no `__pycache__`, `.pyc`, `.pyo`,
or equivalent alternate Python bytecode artifacts.

## 5. Production Python prerequisite

The fixed production interpreter and its standard-library runtime are part of
the pre-source trusted substrate.

Before D10 activation, a protected host qualification must prove the installed
`F:\AITradingBot\runtime` runtime used by the guard is Administrator/SYSTEM
controlled and not writable/replaceable by Trading. The exact interpreter path
and reviewed Python version remain bound in the deployment attestation.

The guard may import only Python standard-library/builtin modules before source
verification. It must not import `trading_bot`, the deployed D10 launcher, or
any module from the sealed source snapshot before verification succeeds.

If the installed production Python runtime cannot be proven non-writable by
Trading, D10 remains BLOCKED.

## 6. Guard verification sequence

Before any governed trading source is imported or executed, the guard:

1. proves its fixed D10 root/source paths and current Trading token;
2. proves fixed D10 root, guard, trust files, and deployed source root security;
3. proves all reserved installing names absent;
4. reads canonical deployment attestation, detached signature, and executable
   manifest through fixed no-follow bounded reads;
5. verifies the detached Architecture-123 P-256 signature;
6. requires the signed guard byte length/SHA-256 to equal its source-owned
   certified guard identity;
7. requires source root, Trading SID, Python identity/version, scheduler
   contract, launcher, manifest count/digest, certified HEAD/tree, and
   deployment ID to satisfy the frozen attestation model;
8. enumerates the complete sealed deployed governed inventory;
9. rejects any extra/missing governed source or alternate bytecode/cache
   artifact;
10. hashes every governed deployed file and requires exact manifest
    byte-length/SHA-256 equality;
11. reinspects root/trust/source identities for drift.

Failure at any point exits without launching D10 source.

## 7. Second-stage execution

Only after successful guard verification may it create one child process:

```text
F:\AITradingBot\runtime\python.exe
  -I
  -S
  -B
  -X
  pycache_prefix=F:\AITradingBot\D10\no-pycache
  F:\AITradingBot\D10\source\scripts\run_personal_desktop_unattended_one_week_soak.py
```

The child receives no market session, decision, account, price, effect, lease,
or path-selection argument.

The guard supplies a sanitized environment and does not place an authority token
or capability in environment variables.

The deployed source remains read-only during the guard/child interval, closing
the verify-to-execute source-upgrade race under the trusted-Administrator threat
model.

## 8. Defense-in-depth A4 verification

Architecture-123 A4 still exists inside the governed source.

The second-stage D10 controller independently rereads/reverifies the deployment
attestation and manifest before any effect gate opens. This is defense in depth,
not the pre-source trust root.

A4 may rely on the fact that the pre-source guard already admitted the immutable
sealed snapshot, but it may not accept a caller/env assertion that the guard
passed.

## 9. Activation lease placement

The later Architecture-122 one-week activation lease is also a fixed
Administrator-protected D10 artifact.

The final launch guard must verify both:

```text
deployment identity valid
AND
activation lease ACTIVE
```

before launching the second-stage D10 source.

An absent, not-yet-active, expired, malformed, conflicting, or deployment-
mismatched lease causes a no-source/no-effect exit.

Task Scheduler's end boundary remains defense in depth.

## 10. Deployment/source separation

Repository source work may define and test:

- launch-guard source;
- scheduler argument contract;
- sealed-source manifest/attestation model revisions;
- pure/mock native guard logic;
- administrator deployment specifications.

Source work does not install the guard, copy source, sign attestations, create
the lease, or mutate Task Scheduler.

Those remain separate protected deployment checkpoints.

## 11. Acceptance criteria

Source acceptance requires tests proving:

- scheduler targets only the fixed installed guard;
- exact `-I -S -B -X pycache_prefix=...` argument vector;
- zero semantic scheduler arguments;
- guard imports no project/deployed-source module before verification;
- guard digest/length are attested;
- signed source root is the sealed D10 source root, not a Git worktree;
- complete deployed inventory rejects missing/extra/cache/bytecode artifacts;
- Trading cannot mutate guard/trust/source objects by policy;
- source cannot be launched when verification fails;
- exactly one fixed second-stage launcher may run after success;
- no authority/capability is passed through environment/CLI;
- Architecture-77 object sets remain unchanged;
- no provider/publication/settlement/recovery/broker/live effect exists in the
  guard.

Architecture 124 completion alone authorizes no production deployment or D10
effect.


## Verified second-stage import bootstrap

The second-stage child intentionally retains `-S`. This means normal
site-package path initialization does not occur automatically.

That is desirable before the sealed launcher executes, but the trading runtime
still requires the repository's reviewed third-party runtime dependencies
(notably `tzdata` on Windows for IANA `zoneinfo` data).

Therefore the future verified second-stage launcher must itself perform one
source-owned import bootstrap before importing any `trading_bot` module:

1. require the exact fixed production interpreter;
2. add only the sealed source package root
   `F:\AITradingBot\D10\source\src`;
3. add only the fixed protected production runtime site-packages directory
   belonging to `F:\AITradingBot\runtime`;
4. do not call `site.main()`;
5. do not process `.pth`, `sitecustomize`, or `usercustomize`;
6. only then import the verified D10/trading modules.

The production-Python substrate qualification therefore covers not only the
interpreter/stdlib but the exact fixed runtime package directory used by this
bootstrap. Trading must not be able to create, replace, rename, delete, or
modify files there.

The guard remains stdlib-only. This bootstrap occurs only after the guard has
verified the sealed source deployment and launched the verified second-stage
script.

## 12. Protected deployment execution-order clarification

The P124 labels identify protected acceptance responsibilities; they are not a requirement to execute the numbered host actions in numeric order.

P124-1 intentionally requires the exact detached-signed Architecture-123 attestation as an input to the production-Python substrate qualification. Because that signed trust material does not exist until the sealed deployment has been provisioned and its attestation has been externally signed/published, the protected operator execution order after S5 is:

```text
P124-2 sealed D10 source/guard provisioning
P124-3 detached signing and trust publication
P124-1 production-Python substrate qualification
P124-4 Trading guard qualification
P124-5 activation lease + scheduler mutation
```

P124-2 and P124-3 remain inert preparation steps: they do not execute the guard, create an activation lease, mutate Task Scheduler, or authorize market-data, decision-publication, settlement, broker-paper, or live effects. P124-1 must PASS before P124-4 or P124-5 may proceed. If P124-1 blocks after trust publication, the published deployment remains inactive and D10 activation is prohibited.

## Protected P124-2 blocked attempt and source reconciliation

The separately authorized P124-2 attempt at
`F:\AI\temp\p1242-provision-continuation-20260925-001413` reached protected
execution and blocked with `native_path_type_acl_or_identity_drift` before any
D10 create. Read-only diagnosis confirmed `F:\AITradingBot\D10` and every
D10 final, reserved, and installing name absent. No production D10 object was
created. The attempt authorization is consumed; no retry is authorized.
The source-only correction separates the protected two-ACE outer parent from
three-ACE D10 objects, corrects Windows early path-policy dispatch and P124-1
ROOT qualification, and requires the actual Trading token's enabled
SeChangeNotifyPrivilege. An inert, explicitly opted-in ACL rehearsal under
`F:\AI\temp` must later PASS before any new P124-2 consideration. The
historical S5-R1 HEAD/TREE pins remain unchanged; governed P124-1 source has
changed, so a fresh S5-R2 exact-tree certification, new operator pins,
manifest, attestation, deployment ID, and byte-exact deployment checkout are
mandatory before a separately authorized protected attempt.
