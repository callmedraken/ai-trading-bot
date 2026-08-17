# Windows production effectful market-data capture

## 1. Scope and decision

C3 connects the reviewed C1 production authority and C2 transactional authority
to exactly one manually invoked, effectful Alpaca daily market-data capture.

C3 does not redesign the C2 relational model, lifecycle states, retry rules,
deterministic identities, lifecycle-arbiter ordering, recovery classifications,
or the distinction between production and test storage. C2 remains durable
authority. C3 supplies the only reviewed production bridge from that authority
to credentials, native process creation, provider transport, child containment,
artifact verification, and successful snapshot authorization.

Production brokerage and real-money trading remain **NO-GO**. C3 authorizes
market-data capture only. It does not add Task Scheduler integration, a daemon,
a polling loop, unattended provider invocation, paper-account mutation, broker
credentials, broker reconciliation, or order submission.

The production composition root is conceptually:

```python
WindowsEffectfulDailySnapshotCapture(
    authority: ValidatedProductionAuthority,
)
```

It owns one `WindowsTransactionalAuthority` bound to the reviewed C3 external
adapter. A normally constructed `WindowsTransactionalAuthority(authority)`
remains effectfully inert. Production effectful capture is not enabled by
supplying an arbitrary adapter or by constructing C2 directly.

## 2. Controlling predecessor contracts

C3 composes the following existing boundaries without weakening them:

- C1 `ValidatedProductionAuthority` owns deployment identity, approved Trading
  SID, signed bootstrap, fixed database/output paths, storage validation, and
  production lifecycle-mutex policy.
- Architecture 77 owns the normalized durable capture state machine, permanent
  provider-call claim, one-shot process/resume fences, conservative recovery,
  and the global lifecycle-arbiter lock order.
- Architecture 81 exposes Architecture-77 semantics through production runtime
  while intentionally leaving real provider, credential, process, resume, and
  snapshot-verification effects unavailable.
- The existing daily-snapshot subsystem owns provider-neutral request/response
  acceptance, canonical snapshot construction, serialization, replay, and
  offline verification.

C3 must preserve the Architecture-77 lock order:

```text
validated immutable reservation identity
-> no caller-owned SQLite transaction
-> acquire reservation lifecycle arbiter
-> re-resolve complete durable active lineage
-> perform and commit one owned BEGIN IMMEDIATE when durable intent/result changes
-> perform external effect with no SQLite transaction active while retaining arbiter
-> persist verified typed result or conservative recovery outcome
-> release arbiter
```

Code must never wait for the lifecycle arbiter while holding a SQLite write
transaction and must never hold a SQLite transaction across `CreateProcessW`,
`ResumeThread`, credential access, provider transport, process wait/termination,
or other native effect.

## 3. Trust and threat boundary

C3 assumes the already-reviewed C1 trusted Trading-token model. It does not
protect against malicious code that already controls the approved Trading token
and can directly access resources granted to that account. It does protect the
reviewed runtime from accidental duplicate effects, ordinary competing approved
processes, caller-selected alternate paths/providers/credentials, malformed or
hostile provider responses, stale process-local capabilities, and crash/restart
ambiguity.

The following are never executable authority:

- filesystem discovery or directory ordering;
- a snapshot filename or pre-existing output file;
- a child PID or exit code by itself;
- child stdout/stderr;
- a child statement that its output is valid;
- a caller-supplied SHA-256 digest;
- environment variables;
- command-line paths or credential material;
- a reconstructed process-local capability after restart;
- raw provider response content.

C3 remains fail-closed when any independently required binding cannot be
established.

## 4. Production request boundary

The caller supplies only nonsecret capture intent compatible with the exact C2
`capture_request/v2` contract. The caller cannot choose or override:

- the authority/database/output root;
- lifecycle-mutex namespace or name;
- provider identity or provider operation;
- Alpaca endpoint or feed implementation;
- credential target names;
- Python executable or child entrypoint;
- Job Object policy;
- process creation flags;
- inherited-handle policy;
- child environment policy;
- final artifact naming policy;
- retry/recovery behavior.

C3 snapshots caller-owned mutable input before deriving identity or allocating
C2 state. The immutable production capture plan binds the exact C2 request,
release, authority epoch, provider descriptor, child protocol, output policy,
and credential policy versions.

## 5. C2 request to daily-snapshot bridge

The C2 request and the existing daily-snapshot request encode different
concepts. C3 freezes their mapping instead of allowing implementation code to
infer it.

For C3 v1:

```text
authorized_snapshot_session =
    latest modeled XNYS trading session in the inclusive interval
    [request_window_start_date, request_window_end_date]

and

authorized_snapshot_session < target_session_date
```

The interval must contain at least one modeled XNYS session. The target session
must satisfy the existing C2 request contract and must not be reinterpreted as
the captured market-data session.

Before the provider-call effect boundary, C3 freezes one factual
`requested_at_utc` and requires the existing daily-snapshot completed-session
derivation from that timestamp to equal `authorized_snapshot_session` exactly.
If the runtime clock and authorized window disagree, C3 fails closed before the
one-shot provider attempt is entered.

The window is therefore authority. The clock is a required reconciliation fact,
not authority to nominate another session.

C3 derives the daily-snapshot request UUID deterministically from reviewed C3
material including the exact C2 reservation/session binding and a fixed
versioned UUID5 material contract. Callers cannot provide a random or unrelated
snapshot request UUID at the effectful boundary.

Existing daily-snapshot acceptance, snapshot identity, canonical serialization,
audit evidence, replay, and offline verification remain authoritative and are
not reimplemented by C3.

## 6. C2 provider-construction meaning in C3

C2's `construct_provider` boundary means **construct and validate the immutable,
nonsecret provider launch plan** when used by C3.

It proves the exact active reservation lineage plus:

- the exact C2 capture request and request digest;
- the authorized snapshot session;
- the public Alpaca daily-snapshot descriptor;
- the fixed child operation version;
- the fixed credential-policy version;
- the fixed output-policy version;
- the approved application release.

It does not read credentials and does not create a credential-backed HTTP
client in the parent. The C2 `ConstructedProvider` remains an opaque
process-local handoff proving that the reviewed nonsecret provider-launch plan
was constructed for that exact reservation.

The real `AlpacaDailySnapshotProvider` is constructed only inside the isolated
child after resume and after child-side Trading-SID verification.

## 7. Secret-free parent and Credential Manager boundary

The parent process is secret-free for the entire C3 lifecycle.

C3 v1 freezes exactly two Windows generic Credential Manager targets:

```text
AITradingBot/MarketData/Alpaca/ApiKeyId/v1
AITradingBot/MarketData/Alpaca/ApiSecretKey/v1
```

They are application-owned generic credentials with local-machine persistence.
C3 reads them only by exact target name. C3 does not enumerate, create, update,
rotate, delete, or otherwise manage them.

Before the first `CredReadW`, the child independently resolves its current token
SID and requires exact equality with the C1-approved Trading SID carried in the
validated child request. A mismatch fails closed before any credential read.

There is no fallback to environment variables, `.env`, configuration files,
command-line secrets, alternate credential names, parent IPC secrets, or a
second credential store.

Native credential buffers are bounded, validated, cleared before `CredFree`
where safely representable, and released exactly once. Python immutable-string
storage cannot be guaranteed to be zeroized and no stronger claim is made.
Secret-bearing Python objects use redacted representations and drop references
on close. Stable errors never contain credential material.

Historical PR #1 is reusable inventory for this narrow reader and its tests only.
Its older scheduling, lineage, capture-attempt, launch-guard, and runner
authority are superseded and must not return through C3.

## 8. Child process preparation and Job Object containment

Before native process creation, the parent prepares:

- one Job Object;
- one bounded parent-to-child request channel;
- one bounded child-to-parent result channel; and
- one parent-owned snapshot staging handle below the validated fixed capture
  output root.

The Job Object is configured before process creation with:

```text
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 1
```

C3 does not permit `JOB_OBJECT_LIMIT_BREAKAWAY_OK` or
`JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`.

C3 uses `STARTUPINFOEXW` and an attribute list containing at least:

```text
PROC_THREAD_ATTRIBUTE_JOB_LIST
PROC_THREAD_ATTRIBUTE_HANDLE_LIST
```

The prepared Job Object is assigned as part of process creation rather than by
a later successful-path `AssignProcessToJobObject` step. This removes the
ordinary suspended-child-created-but-not-yet-job-assigned gap.

C3 may additionally use `PROC_THREAD_ATTRIBUTE_CHILD_PROCESS_POLICY` with
`PROCESS_CREATION_CHILD_PROCESS_RESTRICTED` as defense in depth. Job Object
membership and the active-process limit remain containment authority; the child
process policy is not treated as an independent proof that child-process
creation is impossible under every privileged-token condition.

The process is created with exactly the reviewed flags required by C3,
including:

```text
CREATE_SUSPENDED
EXTENDED_STARTUPINFO_PRESENT
CREATE_UNICODE_ENVIRONMENT
CREATE_NO_WINDOW
```

`lpApplicationName` is the exact absolute approved executable and is never
`NULL`. No shell, `cmd.exe`, PowerShell, file association, PATH lookup, or
caller-selected executable resolution is used.

## 9. Explicit inherited handles

When `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` is used, C3 passes
`bInheritHandles=TRUE` as required by that API and relies on the explicit handle
list to restrict inheritance.

The child receives only the intended inheritable handles:

```text
request read handle
result write handle
snapshot staging write handle
```

No SQLite handle, authority database handle, lifecycle-mutex handle, parent
process handle, Credential Manager handle, brokerage handle, or unrelated
inheritable sentinel handle may be inherited.

Numeric handle values may be transported as nonsecret bootstrap arguments. They
are not authority or deterministic identity material. All semantic child input
arrives through the bounded canonical request channel.

## 10. Explicit child environment

C3 constructs an explicit environment block instead of inheriting the parent
environment. The approved v1 set is narrowly deployment-owned and contains only
values required by the reviewed runtime, initially:

```text
SystemRoot
WINDIR
TEMP=<controlled absolute directory>
TMP=<controlled absolute directory>
PYTHONUTF8=1
```

A future value may be added only by an architecture/acceptance update proving it
necessary.

The child environment contains no Alpaca credentials, broker credentials,
`PYTHONPATH`, provider endpoint override, proxy override, certificate override,
developer/Codex variables, profile path used as authority, or arbitrary parent
environment entry.

## 11. Process-local native handle registry

C2 persists canonical process/result evidence, not live native handles. C3 owns
a private nonserializable process-local registry keyed by original
reservation/execution provenance.

A live entry may retain only runtime resources required for the in-progress
capture, including:

- process handle;
- primary-thread handle;
- Job Object handle;
- parent pipe endpoints;
- staging handle/identity;
- native lifecycle state.

The registry cannot be reconstructed from SQLite, a PID, an artifact, or child
output. Process death destroys it.

If the parent dies, Job Object close semantics terminate a surviving associated
child when the final job handle closes. Restart then follows C2 durable recovery
and never recreates lost process/resume/snapshot capabilities.

## 12. Process-intent and suspended-creation ordering

The durable order remains:

```text
C2 launch reservation COMMITTED
-> C3 nonsecret provider-launch plan constructed
-> C2 PROCESS_INTENT_COMMITTED
-> native CreateProcessW(CREATE_SUSPENDED)
-> typed process result
-> C2 process-result persistence
-> PRE_RESUME_READY
```

A successful C3 process receipt may be issued only after the reviewed native
adapter proves all required pre-resume facts, including successful suspended
creation and successful Job Object association by the process-creation
attribute contract.

A definitive `ProcessCreationFailure` with outcome `NOT_CREATED` may be issued
only when C3 can prove no child was created. Any state in which process creation
may have succeeded without a persistable typed result remains conservative and
uses the existing C2 unknown-process recovery.

Live handles remain process-local and are never placed into canonical C2
process evidence.

## 13. Resume ordering

The order remains:

```text
PRE_RESUME_READY
-> C2 commit ResumeIntent
-> exact C3 resume capability
-> ResumeThread(exact primary-thread handle)
```

The successful `ResumeThread` return must report a previous suspend count of
exactly one. A failure value or unexpected suspend count is fail-closed and does
not authorize a second resume attempt.

The in-memory C2/C3 resume receipt is retained while the child executes. C3 does
not immediately persist `RESUME_RECORDED` merely because `ResumeThread`
returned successfully.

C3 first obtains a bounded child outcome or timeout/termination classification,
performs required process/pipe/Job cleanup, constructs exact sanitized cleanup
evidence, and only then persists C2 post-resume plus cleanup evidence.

`RESUME_RECORDED` therefore means the reviewed resume occurred and C3 reached a
known post-resume cleanup observation. It does not mean the provider call or
snapshot succeeded.

## 14. One-shot child provider-attempt fence

After resume, the child may perform at most one C3 provider attempt.

The child crosses an explicit one-shot logical fence named conceptually:

```text
C3_PROVIDER_ATTEMPT_ENTERED
```

Once this fence is entered, that C2 claim is consumed for C3 purposes even if a
later failure occurs during SID reconciliation, credential retrieval, provider
construction, TLS/HTTP transport, response parsing, snapshot acceptance,
serialization, or staging.

For C3, `provider_call_disposition=CONFIRMED` means the one authorized C3
provider attempt definitively crossed that fence. It does **not** assert that
Alpaca's remote server definitely received an HTTP request.

If the parent cannot establish whether the child crossed the fence, the outcome
is `MAY_HAVE_OCCURRED` and no retry is authorized.

The fence exists to make retry semantics conservative and explicit. It cannot be
reset, reacquired, reconstructed, or bypassed by a different provider object.

## 15. Fixed child execution sequence

The reviewed child executes this bounded sequence:

```text
read bounded canonical child request
-> enter one-shot C3 provider-attempt fence
-> reconcile exact request/protocol/release bindings
-> verify current Trading SID
-> CredReadW exact API-key target
-> CredReadW exact secret target
-> construct scoped private credential holder
-> construct exact existing Alpaca daily-snapshot provider
-> invoke exactly one provider fetch
-> existing strict provider-response parsing
-> existing deterministic daily-snapshot acceptance
-> canonical snapshot serialization
-> child-side in-memory snapshot verification
-> write candidate canonical bytes to inherited staging handle
-> flush staging handle
-> emit one bounded sanitized canonical child result
-> release credential/native resources
-> exit
```

There is no retry, reconnect policy, alternate provider, fallback feed, alternate
endpoint, pagination continuation that causes a second HTTP request, or child
self-relaunch.

## 16. Child result contract

The child result is evidence, never authority. It has one fixed schema/version,
canonical serialization, a bounded byte limit, and a closed classification set.

The v1 classification vocabulary is:

```text
SUCCEEDED
REQUEST_INVALID
SID_REJECTED
CREDENTIAL_FAILED
TRANSPORT_FAILED
HTTP_FAILED
PROVIDER_RESPONSE_INVALID
SNAPSHOT_REJECTED
SERIALIZATION_FAILED
STAGING_FAILED
INTERNAL_FAILED
```

The result binds the exact child request/reservation/execution and may contain
only stable sanitized facts such as:

- child protocol version;
- provider-attempt-fence state;
- classification;
- sanitized HTTP status when available;
- sanitized numeric provider code/request identifier when safe;
- claimed snapshot UUID;
- claimed artifact SHA-256 and byte length;
- cleanup classification;
- native child-exit classification.

It never contains credential material, raw provider bodies, raw exception text,
tracebacks, environment dumps, stdout/stderr, arbitrary paths, or persisted live
HANDLE values.

Every snapshot claim from the child is untrusted until independently verified
by the parent.

## 17. Parent-owned staging

The caller never supplies a snapshot destination. The destination is the fixed
C1-validated capture-output root.

Before `CreateProcessW`, the parent exclusively creates one staging object below
that root and retains its identity. A deterministic transport name such as:

```text
.c3-capture-<launch-reservation-id>.staging
```

may be used. The staging name/path is transport and cleanup material only and is
not snapshot identity.

The child receives only a write handle for that exact staging object. It cannot
nominate a different path, directory, or final filename.

## 18. Parent-independent snapshot verification and publication

Child `SUCCEEDED` is insufficient for C2 success.

After child execution and revocation/closure of child write access, the parent
independently:

1. validates the retained staging identity;
2. reads the bytes through the reviewed fixed-root boundary;
3. enforces the snapshot byte limit;
4. computes SHA-256;
5. runs the existing offline daily-snapshot verifier;
6. reconciles the exact C3/C2 request;
7. reconciles the exact authorized snapshot session;
8. reconciles the exact provider descriptor and ordered universe;
9. requires canonical snapshot bytes;
10. requires child snapshot claims to match the independently derived facts;
11. publishes the final artifact with no-clobber semantics below the fixed root;
12. reopens/revalidates the final object and exact bytes.

The final filename remains the established canonical form:

```text
daily-market-data-snapshot-<snapshot-id>.json
```

No caller-selected output name is allowed.

A pre-existing final or staging collision fails closed. C3 never silently
replaces an existing artifact.

## 19. `VerifiedCapturedSnapshot` authorization

Only successful parent verification issues an opaque process-local
`VerifiedCapturedSnapshot`.

It binds at least:

- C2 session ID;
- attempt ID;
- claim ID;
- launch-reservation ID;
- launch-execution ID;
- snapshot UUID;
- final artifact SHA-256;
- final artifact byte length;
- final artifact identity evidence;
- private C3 verifier issuer/service provenance;
- one-shot terminal authorization.

It cannot be directly constructed, copied into authority, serialized, pickled,
reconstructed from public fields, or recreated after restart.

For C3 v1:

```text
C2 terminals.snapshot_digest =
    SHA-256(exact canonical finalized snapshot artifact bytes)
```

The source/provider-body digest remains separate snapshot audit evidence and is
never substituted for the terminal snapshot digest.

A C3 caller cannot invoke successful terminal recording by supplying an
arbitrary 32-byte digest. The C3 success path accepts only the exact live
`VerifiedCapturedSnapshot` bound to that reservation and consumes it once.

## 20. Additive C2 production-evidence seam

C3 does not require a SQL/schema migration.

Current C2 runtime deliberately uses deterministic fixture-style cleanup and
terminal diagnostic evidence because C2 had no real production side-effect
adapter. C3 requires narrow additive production evidence injection at the
reviewed facade/service boundary for real post-resume cleanup and terminal
sanitized evidence.

This extension must preserve:

- the existing SQL columns and production SQL artifact;
- all existing C2 states and transition predicates;
- the existing lifecycle arbiter;
- one owned `BEGIN IMMEDIATE` per durable transition;
- exact canonical bytes plus SHA-256 evidence pairs;
- existing C2 recovery actions;
- existing test fixture semantics unless explicitly routed through C3.

C3-issued cleanup/diagnostic evidence is privately issued, exact-reservation or
exact-execution bound, canonical, sanitized, one-shot where authority-bearing,
and validated before persistence.

This is a C3 integration seam, not a redesign of C2 authority.

## 21. Terminal mapping

C3 maps reviewed outcomes into the existing C2 terminal matrix:

| C3 outcome | C2 outcome |
| --- | --- |
| definitive native process not-created result | `FAILED / NOT_STARTED`, no snapshot |
| suspended process persisted but abandoned before resume intent | `CLASSIFY_PRE_RESUME_READY`, conservative manual review/close |
| process intent committed but native creation result unresolved | `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` |
| resume intent committed but resume/post-resume result unresolved after restart | `CLASSIFY_RESUME_OUTCOME_UNKNOWN` |
| current process proves resume occurred but child/provider outcome is unresolved | `AMBIGUOUS / MAY_HAVE_OCCURRED`, no snapshot |
| definitive post-fence child failure | `FAILED / CONFIRMED`, no snapshot |
| parent snapshot verification/publication failure after definitive child outcome | `FAILED / CONFIRMED`, no snapshot |
| exact final artifact independently verified and live verifier capability retained | `SUCCEEDED / CONFIRMED`, exact artifact SHA-256 |
| successful terminal selected | existing C2 selection path |

A non-success terminal never carries a snapshot digest.

## 22. Crash and restart semantics

No process-local C3 capability survives or is reconstructed after restart.

Existing C2 durable states remain the recovery authority:

```text
COMMITTED
    -> CLASSIFY_LAUNCH_RESERVATION

PROCESS_INTENT_COMMITTED without definitive persisted process result
    -> CLASSIFY_PROCESS_OUTCOME_UNKNOWN

PROCESS_CREATED / PRE_RESUME_READY
    -> CLASSIFY_PRE_RESUME_READY

PROCESS_CREATED / RESUME_INTENT_COMMITTED without definitive persisted post-resume result
    -> CLASSIFY_RESUME_OUTCOME_UNKNOWN
```

A restart never scans capture-output to reconstruct a provider permit, process
result, resume result, `VerifiedCapturedSnapshot`, terminal success, or retry
authority.

A final artifact that exists after a parent crash but whose success terminal was
not durably committed is historical evidence only. Even if it parses and hashes
correctly, it cannot be automatically promoted into executable authority.

A committed successful terminal awaiting selection continues through the
existing C2 `SELECT_COMMITTED_SUCCESS` recovery/selection contract.

## 23. Cleanup and ambiguity

Every native resource acquired by C3 has one explicit owner and exactly-once
cleanup policy. Failure to clean one resource does not silently skip independent
cleanup of remaining resources.

Cleanup diagnostics are stable and secret-free. Raw Windows error messages,
provider bodies, exception text, environment contents, and HANDLE values are not
persisted as authority evidence.

Timeout after resume is conservative. C3 may use `TerminateJobObject` and a
bounded termination-wait policy to contain the child, but termination does not
prove that a provider attempt did not occur and does not authorize retry.

If the current process can definitively observe the provider-attempt fence and
child failure after resume, it may persist the corresponding confirmed failure.
If it cannot establish the required fact, ambiguity wins.

## 24. Manual-only operation

C3 exposes one manually invoked, one-shot production capture operation.

It does not add Task Scheduler, scheduler credentials, service/daemon mode,
trusted exchange-hours scheduling authority, automatic retries, unattended
recovery, alert delivery, or background loops.

Those concerns remain later roadmap milestones after reliable manual capture and
manual paper-cycle execution have been proven.

## 25. Historical PR #1 reuse policy

Historical PR #1 is not mergeable authority for C3. It is a source of reviewed
implementation ideas only.

C3 may selectively port and re-review:

- exact Windows Credential Manager reads and bounded cleanup;
- current-process SID inspection;
- stable secret-free child error classifications;
- one-call provider fencing;
- useful native process wrapper/test patterns.

C3 must not restore PR #1's:

- local lineage-head authority;
- capture-attempt authority;
- readiness/scheduling authority;
- old launch mutex authority;
- old guarded runner orchestration;
- caller-selected artifact authority.

C1/C2 supersede those boundaries.

## 26. C3 completion criterion

C3 is complete only when the following statement is supported by deterministic
tests and native Windows acceptance evidence:

> From one exact C1-approved Trading process, one manually invoked nonsecret
> request can cause at most one C2-authorized provider attempt; secrets exist
> only inside the contained child; process creation and resume obey the durable
> C2 fences; every ambiguous crash fails closed without automatic retry; and
> only a parent-independently verified canonical artifact in the fixed C1
> capture-output root can become the selected C2 snapshot.

Passing one Alpaca HTTP request is insufficient to complete C3.

## 27. Explicit non-goals

C3 does not implement:

- Task Scheduler or unattended capture;
- official production XNYS-hours scheduling authority;
- paper-account state mutation;
- target generation or strategy execution;
- brokerage adapters or broker reconciliation;
- broker credentials;
- order submission/cancel/replace;
- real-money execution;
- multi-host authority;
- cloud coordination;
- automatic ambiguous-operation repair;
- automatic discovery/promotion of orphaned artifacts;
- a GUI.

The next milestone after C3 is the reliable manually invoked paper cycle:
verified C3 snapshot -> strategy -> proposals -> deterministic risk -> paper
execution -> durable before/after evidence.
