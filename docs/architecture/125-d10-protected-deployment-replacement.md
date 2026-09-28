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

For this one-time S5-R8 -> S5-R10 replacement lineage, item 7 is a frozen
historical source fact, not a caller assertion and not a host-state inference.
The accepted project status/handoff at the Architecture-125 freeze records that
P124-5 was not run and that no D10 activation lease or D10 scheduler mutation
occurred. The implementation must represent this as an explicit source-owned
closed value for this exact lineage; it must not manufacture the fact by
blanket-setting every AdmissionFacts field to true.

That frozen historical fact may contribute
`no_prior_d10_activation_or_scheduler_mutation=True` only when the same fresh
admission also proves the exact historical S5-R8 canonical deployment, exact D5
capture-only scheduler predecessor, and absent activation/cache objects. Any
future accepted P124-5 execution, or any replacement lineage after this one,
invalidates this frozen fact and requires a new reviewed architecture/source
identity before protected replacement may proceed.

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

Both are same-volume destination-absent renames with no overwrite semantics.

The exact native publication mechanism is handle-pinned, following the already
accepted Architecture-78 authority-publication pattern rather than a path-only
`MoveFileW` call:

1. the source directory for the current rename step is opened with
   `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS` and the access
   required for handle-based rename, including `DELETE`;
2. that source handle remains open from its final no-follow identity/security/
   volume verification through the rename call;
3. the already verified `F:\AITradingBot` parent is also held by an open
   no-follow directory handle across the rename;
4. immediately before mutation, the implementation re-inspects both open
   handles and requires the exact previously admitted source identity and exact
   protected parent identity to remain unchanged;
5. publication uses `SetFileInformationByHandle(..., FileRenameInfo, ...)`
   on the still-open source handle, not `MoveFileW`;
6. `FILE_RENAME_INFO.ReplaceIfExists` is exactly false;
7. `FILE_RENAME_INFO.RootDirectory` is the still-open verified
   `F:\AITradingBot` parent handle and `FileName` is only the fixed,
   source-owned destination leaf for that rename step;
8. no absolute/caller-selected destination is accepted by the mutation
   primitive;
9. after native success and before either pinned handle is closed, the source
   handle is re-inspected and must now resolve to the exact fixed destination
   while preserving the same volume serial/file identity/security facts; the
   parent handle must also still match its admitted identity;
10. only that verified native-success result may be reported as
    `MutationOutcome.SUCCESS`.

A source handle opened and verified earlier but closed before a path-based
rename is not sufficient for P125. The object verified is the object renamed.

A native false return, exception, unavailable result, post-call identity
mismatch, cleanup/handle-close ambiguity, or any inability to prove that the
pinned object became the exact fixed destination is
`MutationOutcome.INDETERMINATE`. The ordinary replacement state machine
never retries such a mutation automatically.

The destination-absence precheck remains required, but it is defense in depth:
kernel-level no-replace behavior is the authoritative collision guard at the
rename call. If the destination appears after precheck,
`ReplaceIfExists = FALSE` must cause the rename to fail rather than replacing
it.

This contract deliberately makes no additional directory-entry durability
claim beyond the accepted Architecture-78 model. Staging file contents must be
flushed before they are admitted, but no extra user-mode directory flush is
invented for the rename. Abrupt process/system failure at any publication
window is handled by the Architecture-125 namespace classifier on the next
invocation; uncertainty never creates retry authority.

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

## 8.1 P125-R1G explicit recovery after first-step indeterminate + exact OLD_CANONICAL reclassification

The first protected P125-R1 replacement attempt on 2026-09-27 returned:

    status = BLOCKED
    reason_code = INDETERMINATE_MUTATION
    completed_renames = []
    highest_definitely_completed_namespace_state = OLD_CANONICAL

That transcript did not prove whether the native first rename occurred. A fresh
independent two-pass namespace observation then proved exactly:

    OLD_CANONICAL
    canonical = exact historical S5-R8
    staging = exact S5-R10
    retired = absent
    unexpected reserved names = absent
    D5 scheduler predecessor = exact

A second read-only pre-call diagnostic reproduced the complete first-rename
precondition boundary without calling `SetFileInformationByHandle`:

- fresh full admission = exact OLD_CANONICAL;
- every AdmissionFacts predicate = true;
- parent handle open = success;
- canonical source handle open = success;
- pinned parent/source identities = exact admitted identities;
- same volume serial/root = true;
- retired destination = absent;
- repeated pinned parent/source inspection = stable;
- fixed FILE_RENAME_INFO buffer construction = exact fixed retired leaf;
- ReplaceIfExists = false;
- RootDirectory = the pinned parent handle;
- source/parent close = success with no ambiguity.

Therefore P125-R1G narrows the unresolved fault domain to the native rename call
or the immediately subsequent verification/close path. The existing operator
must not be rerun unchanged.

### 8.1.1 No automatic retry authority

Fresh exact OLD_CANONICAL proves that the prior attempt left no committed
namespace transition. It does not by itself authorize an automatic retry.

One additional protected retry may be considered only after:

1. R1G diagnostic source is implemented, exact-reviewed, and canonically
   certified;
2. the operator again proves exact OLD_CANONICAL and the complete frozen
   Architecture-125 admission immediately before mutation;
3. the human explicitly authorizes the R1G recovery attempt.

OLD_RETIRED, NEW_CANONICAL, or CONFLICTING remains a hard stop and is not
eligible for this recovery path.

### 8.1.2 Native failure diagnostics

The R1G native wrapper must preserve fail-closed behavior while retaining one
bounded diagnostic from a failed Windows rename call.

Immediately before `SetFileInformationByHandle(..., FileRenameInfo, ...)` the
ctypes saved last-error slot is cleared. If and only if the native call returns
false, the wrapper must capture `ctypes.get_last_error()` immediately, before
any other native/API call can overwrite it.

The diagnostic surface is bounded and sanitized:

- fixed rename step;
- closed failure stage;
- unsigned Win32 error code in the range 0..0xffffffff.

It must not expose paths beyond the already frozen step identity, raw exception
text, handles, ACLs, SIDs, arbitrary host strings, or caller-controlled data.

A false native return remains `MutationOutcome.INDETERMINATE`; the error code
is diagnostic only and grants no retry authority.

For a true native return, saved last-error content is ignored as undefined/stale
and the existing post-call pinned identity checks remain mandatory.

### 8.1.3 Closed failure-stage taxonomy

R1G may distinguish only these closed stages:

    PRE_CALL
    NATIVE_FALSE
    POST_CALL_VERIFY
    CLOSE_AMBIGUITY

No raw exception class/text is emitted. Any unclassified exception collapses
to PRE_CALL or POST_CALL_VERIFY according to whether the native rename call had
already reported success.

### 8.1.4 Recovery-attempt semantics

The R1G protected recovery operator remains one invocation with at most the two
existing fixed renames in the original order.

If the first native rename returns false:

- stop immediately;
- emit BLOCKED / INDETERMINATE_MUTATION plus the bounded R1G diagnostic;
- do not attempt the second rename;
- do not retry;
- do not rollback;
- perform only fresh read-only namespace classification after handles close.

If the first rename reports success and the existing pinned post-call/close
proof succeeds, continue only under the existing second-step revalidation and
fixed staging-to-canonical rename contract.

If the second rename is indeterminate, preserve the existing OLD_RETIRED
highest-definitely-completed-state semantics and stop without retry/rollback.

A PASS still requires the unchanged post-publication verification and leaves
canonical S5-R10 unsigned/inactive with historical S5-R8 retired.

### 8.1.5 Diagnostic evidence is not trust or activation authority

R1G adds no signing, trust-publication, activation-lease, scheduler-mutation,
provider, Paper-v2, broker, or live authority. It does not change the fixed
paths, source/staging bytes, D5 scheduler contract, no-replace behavior, or
post-publication invariants.

Microsoft documents that `SetFileInformationByHandle` returns zero on failure
and that extended error information is obtained through `GetLastError`. R1G
uses only that bounded diagnostic to characterize the already reviewed native
call; it does not weaken the mutation fence.

## 8.2 P125-R1H native rename transport diagnosis before any further protected attempt

The separately authorized and canonically certified R1G recovery attempt on
2026-09-27 again stopped at the first OLD_TO_RETIRED mutation. Its bounded
diagnostic was:

    stage = NATIVE_FALSE
    step = OLD_TO_RETIRED
    win32_error = 87 (ERROR_INVALID_PARAMETER)

The R1G process then exited BLOCKED with zero completed renames and
OLD_CANONICAL as the highest definitely completed state.

A fresh independent two-pass observation after that failed call proved exactly:

    OLD_CANONICAL
    canonical = exact historical S5-R8
    staging = exact S5-R10
    retired = absent
    unexpected reserved names = absent
    D5 scheduler predecessor = exact

Therefore the R1G recovery authorization is consumed and no further protected
retry is authorized. The new evidence localizes the defect to the submitted
SetFileInformationByHandle(FileRenameInfo) call boundary, but Win32 error 87 by
itself does not prove which parameter or representation is incompatible with
this host.

Microsoft documents all of the following:

- SetFileInformationByHandle uses FileRenameInfo for FILE_RENAME_INFO and
  returns zero on failure with GetLastError carrying extended error;
- FILE_RENAME_INFO permits RootDirectory to be a directory handle when FileName
  is relative;
- FILE_RENAME_INFORMATION likewise carries ReplaceIfExists, RootDirectory,
  FileNameLength, and a relative FileName;
- NtSetInformationFile with FileRenameInformation (10) consumes
  FILE_RENAME_INFORMATION and requires DELETE access on the source handle.

R1H therefore separates host-mechanism discovery from production authority.
The next checkpoint is a disposable-native acceptance harness only. Production
F:\AITradingBot rename wiring remains frozen until that host evidence is
reviewed.

### 8.2.1 R1H-A disposable acceptance matrix

R1H-A may create and rename only uniquely named disposable directories below:

    F:\AI\temp\p125-r1h-native-acceptance-<random-or-guid>

It must reject F:\AITradingBot, every Architecture-125 canonical/staging/
retired path, and any caller-selected production path. The disposable root must
be created by the harness itself and positively proven outside F:\AITradingBot
before any rename call.

R1H-A tests the Windows-host rename mechanism, not D10 identity, trust, ACL, or
scheduler authority. Each matrix case uses a fresh disposable parent/source/
destination triple so one case cannot affect another.

The minimum matrix is:

1. WIN32_FROZEN_CONTROL
   - SetFileInformationByHandle;
   - FileRenameInfo (3);
   - current frozen FILE_RENAME_INFO representation;
   - non-NULL pinned RootDirectory;
   - fixed relative destination leaf;
   - ReplaceIfExists false.

2. WIN32_EXACT_LENGTH
   - same Win32 API and pinned handles;
   - same FILE_RENAME_INFO fields;
   - buffer length passed as the exact byte range through the final FileName
     byte: FIELD_OFFSET(FileName) + FileNameLength;
   - no terminating NUL counted in FileNameLength.

3. NT_NATIVE_ANCHORED
   - user-mode NtSetInformationFile;
   - FileRenameInformation (10);
   - exact FILE_RENAME_INFORMATION representation;
   - same pinned source handle and pinned parent handle;
   - fixed relative destination leaf;
   - ReplaceIfExists false;
   - IO_STATUS_BLOCK supplied and captured.

An optional diagnostic-only Win32 case with RootDirectory NULL and an absolute
disposable destination may be added solely to isolate API behavior. It is never
a production candidate because it drops the pinned-parent destination
authority.

No matrix result grants production retry authority.

### 8.2.2 Exact native-call evidence

For every disposable case, the harness must record only bounded source-owned
evidence:

- case enum;
- API enum;
- buffer size;
- FileNameLength;
- whether RootDirectory was non-NULL;
- BOOL result + immediate Win32 error for Win32 cases;
- raw 32-bit NTSTATUS + IO_STATUS_BLOCK status/information for the Nt case;
- fresh post-call source/destination presence;
- same-object proof when the rename reports success.

No raw handles, ACLs, SIDs, arbitrary paths, exception text, or reusable
authority may appear in the transcript.

Win32 failure evidence captures GetLastError immediately after a zero return.
Nt failure evidence captures the NtSetInformationFile return NTSTATUS directly;
no RtlNtStatusToDosError conversion is required for authority or acceptance.

For the Nt case, STATUS_SUCCESS (0) is the only accepted positive mutation
result for R1H-A. Any nonzero return, STATUS_PENDING, malformed IO_STATUS_BLOCK,
post-call identity mismatch, or close ambiguity is non-PASS evidence for that
case.

### 8.2.3 Disposable success proof and cleanup

A disposable case is SUCCESS only when:

1. its source and parent handles were opened successfully with the intended
   fixed access/share/no-follow semantics;
2. the destination was absent before the call;
3. the call returned its exact success result;
4. the pinned source handle re-resolves to the exact destination leaf and same
   file identity/volume after the call;
5. the pinned parent remains the same object;
6. a fresh path observation proves source absent and destination present as the
   same object;
7. all opened handles close successfully.

Harness cleanup occurs only inside the disposable acceptance root after all
case evidence is frozen. Cleanup failure does not convert a rename case into
success and must be reported separately. The harness never invokes P125
replacement, recovery, signing, activation, scheduler, provider, paper, broker,
or live code.

### 8.2.4 Production transport remains undecided until host evidence

R1H-A must not modify _set_fixed_rename, _rename_fixed_step,
p125_replace_d10, or p125_recover_d10 production behavior.

After R1H-A source review and focused verification, the user runs the disposable
native acceptance harness locally. ChatGPT then reviews the exact result and
freezes R1H-B:

- if WIN32_EXACT_LENGTH succeeds with the pinned parent contract, prefer the
  narrower Win32 buffer-length correction;
- otherwise, if NT_NATIVE_ANCHORED succeeds exactly, R1H-B may replace only the
  failing production rename transport with the reviewed NtSetInformationFile
  primitive while preserving all Architecture-125 pre/post identity,
  same-volume, destination-absence, no-replace, single-attempt, and fail-closed
  rules;
- if neither anchored mechanism succeeds exactly, no production retry is
  considered and architecture returns to diagnosis.

The optional absolute-path Win32 diagnostic can never be selected as the
production transport.

Any R1H-B production source change requires focused verification, exact GitHub
review, replacement canonical three-lane certification, fresh exact
OLD_CANONICAL preflight, and a new explicit human authorization. No prior R1F
or R1G authorization carries forward.

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

### 10.1 Frozen retired-tree deletion mechanism

The retirement cleanup uses the legacy handle-based Windows disposition
contract already present in the reviewed native runtime:

- targets are opened with `CreateFileW` using `FILE_FLAG_OPEN_REPARSE_POINT`;
- directory targets additionally use `FILE_FLAG_BACKUP_SEMANTICS`;
- the target handle requests `DELETE`, `READ_CONTROL`,
  `FILE_READ_ATTRIBUTES`, and `SYNCHRONIZE`;
- file targets additionally request the read access needed to re-hash the exact
  expected bytes through the same pinned handle;
- directory targets additionally request the list/traverse access needed to
  prove the exact expected child inventory through the same pinned handle;
- the destructive target handle uses share mode 0. Failure to obtain exclusive
  access blocks rather than broadening the sharing contract;
- deletion is requested only with
  `SetFileInformationByHandle(FileDispositionInfo)` and
  `FILE_DISPOSITION_INFO.DeleteFile = TRUE`;
- `FileDispositionInfoEx`, POSIX-delete semantics, `DeleteFileW`,
  `RemoveDirectoryW`, shell recursion, generic recursive deletion, and
  caller-selected deletion paths are not P125 authorities.

The object verified is the object marked for deletion. A target is not reopened
by pathname for the destructive call after its verified handle is closed.

The direct parent directory is also opened no-follow and retained across each
delete step. It is re-inspected immediately before the disposition call and
again after the target handle is closed. The parent handle may use the
read/list rights and sharing necessary to remain open while the child is
deleted, but it grants no caller-selected mutation authority.

For a file target, the pinned destructive handle must reproduce the exact
frozen byte length and SHA-256 already admitted for that path before
`DeleteFile=TRUE`.

For a directory target, the pinned destructive handle must reproduce the exact
expected child inventory before `DeleteFile=TRUE`. The retired root and every
subdirectory are therefore deleted only after all expected children have been
positively deleted.

### 10.2 Frozen cleanup plan and ordering

Before the first destructive call, the operator performs a complete fresh
cleanup admission and freezes one immutable in-process cleanup plan.

The plan is constructed only from source-owned fixed paths plus the exact,
already verified historical S5-R8 signed manifest/trust identity. Untrusted
directory enumeration may validate the plan but never generates deletion
targets.

The plan contains exactly:

1. every historical S5-R8 source file named by the verified executable
   manifest;
2. the fixed historical launch guard;
3. the fixed historical attestation and detached signature;
4. the fixed historical executable manifest;
5. every source directory implied by the manifest paths;
6. the fixed retired `source` directory;
7. the fixed retired root.

No other target may enter the plan.

Deletion order is deterministic and bottom-up:

1. source files in canonical manifest-path order;
2. launch guard;
3. attestation;
4. detached signature;
5. executable manifest last among files;
6. implied source directories deepest-first, with deterministic ordinal
   tie-breaking;
7. `source`;
8. retired root last.

The manifest is retained until all manifest-bound files have been positively
deleted. Once deletion begins, the frozen in-process plan, not a newly observed
directory inventory, determines the remaining targets.

### 10.3 Per-target commit point

One delete step is SUCCESS only when all of the following hold:

1. the fixed direct parent and fixed target are opened no-follow;
2. both pinned handles reproduce the admitted native identity/security/volume
   facts immediately before mutation;
3. the target reproduces its exact expected bytes or exact empty/expected
   directory inventory;
4. `SetFileInformationByHandle(FileDispositionInfo, DeleteFile=TRUE)`
   returns success;
5. the target handle closes successfully;
6. while the verified parent handle remains open, a fresh direct-parent
   inventory omits the exact target leaf;
7. a fresh no-follow open of the exact target is absent, with absence accepted
   only together with the still-exact direct-parent proof;
8. the direct-parent handle still reproduces the exact admitted parent
   identity/security/volume facts.

Only then may the same invocation advance to the next frozen target.

A false native return, exception, target-handle close ambiguity, unexpected
continued presence, parent drift, or inability to prove exact absence is
INDETERMINATE. The current invocation stops immediately and does not retry the
same target, skip it, reconstruct it, roll back prior deletions, or continue to
later targets.

Windows documents FileDispositionInfo as marking the opened object for deletion
when the handle is closed and requires DELETE access for DeleteFile=TRUE. P125
treats successful handle close plus independent parent/path absence proof as
the commit point; it does not treat the disposition call alone as deletion
proof.

### 10.4 Partial cleanup and later invocations

Same-invocation forward progress is allowed only after each prior target has
reached the exact SUCCESS commit point above. This is continuation of one
admitted cleanup operation, not retry authority.

A later invocation must begin with fresh read-only classification:

- FULL_RETIRED: the complete exact S5-R8 retired tree is still present. The
  ordinary cleanup may start again after all cleanup admission facts are
  freshly reproved.
- PARTIAL_RETIRED: the retired root exists but is not the complete exact S5-R8
  tree. Even if the remaining objects are a clean subset of the frozen plan,
  the ordinary cleanup MUST NOT continue. It returns
  SEPARATE_RECOVERY_REQUIRED.
- RETIRED_ABSENT: the retired root is absent. If every post-cleanup invariant is
  freshly exact, the operator may return an idempotent read-only cleanup PASS;
  it performs no mutation.
- CONFLICTING: any unexpected object, identity/security drift, unclassifiable
  namespace, or ambiguous observation blocks.

R1E does not implement a PARTIAL_RETIRED recovery command. Any future recovery
authority is a separate reviewed checkpoint.

### 10.5 Cleanup admission and final proof

Before FULL_RETIRED deletion begins, the cleanup operator must freshly prove:

- canonical S5-R10 is exact and its P124-3 signed trust verifies exactly under
  the frozen production key;
- canonical activation lease/installing/tmp and cache objects are absent;
- the D5 Task Scheduler predecessor remains exact;
- the protected `F:\AITradingBot` parent remains exact;
- retired S5-R8 guard/source/manifest/attestation/signature are exact and the
  historical signature verifies;
- retired inventory equals the frozen plan exactly, including case;
- canonical and retired roots are on the same accepted local NTFS volume;
- no staging root and no unexpected replacement/retired sibling exists.

After the retired root SUCCESS step, cleanup PASS requires two fresh matching
read-only observations proving:

- retired root absent;
- canonical S5-R10 signed deployment still exact;
- canonical activation/cache still absent;
- D5 scheduler predecessor still exact;
- protected parent still exact;
- staging absent;
- no unexpected replacement/retired sibling exists.

No cleanup step grants signing, activation, scheduler, provider, paper, broker,
or trading authority.

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
