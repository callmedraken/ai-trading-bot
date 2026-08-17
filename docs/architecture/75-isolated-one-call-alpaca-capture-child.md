# Isolated one-call Alpaca capture child

## Milestone boundary

This milestone implements only a manually invoked child and a separate,
secret-free Windows parent launcher. The caller supplies one already-published
`CaptureAttemptAllocationRecord`; neither command allocates or advances
anything.

There is no integration with guarded readiness, attempt-history advancement,
terminal or snapshot selection, the launch mutex, Task Scheduler, lineage,
paper operation, retry, a service, or background orchestration. The child
result and process records are historical facts. They do not authorize a retry
or prove zero provider calls.

Unattended provider use remains **NO-GO**.

## Strict child request

`IsolatedCaptureChildRequest` schema 1 contains the exact allocation evidence
and transport path, deterministic attempt UUID and ordinal, scheduled session
and launch UUIDs, exact credential-reference evidence and path, snapshot
request UUID, capture-configuration evidence and path, and:

- ordered symbols exactly `SPY`, `QQQ`;
- the exact `XNYS` calendar descriptor;
- `1D`, `RAW`, policy provider `ALPACA_MARKET_DATA`, adapter version 1,
  approved historical-bars operation, `SIP`, and `USD`;
- target session, explicit UTC request timestamp, and its New York date;
- socket timeout 15 seconds and default wall timeout 30 seconds;
- response limit 4 MiB and candidate limit 100;
- exact snapshot-destination and software-release evidence;
- absolute destination and result transport paths; and
- child operation `isolated-alpaca-capture-child-v1`.

The allocation, credential reference, capture configuration, request identity,
target/date, universe, provider descriptor, feed, currency, and one-call budget
must all reconcile before credential access. Paths are serialized transport
metadata but excluded from UUID5 material.

The UUID5 namespace is `4f31015f-5b34-5b37-98cc-4a64fe1d3490`, with material
version `isolated-capture-child-request-v1`. Identity material is explicitly
UTF-8 byte-length framed. JSON is compact, sorted, ASCII-safe, strict, and ends
with one newline. Parsing rejects BOMs, duplicate/unknown/missing members,
floats, constants, noncanonical values, and noncanonical bytes.

## Windows credential boundary

`WindowsCredentialManagerReader` accepts only a verified
`WindowsMarketDataCredentialReference`. Its native adapter uses exact
current-process token SID inspection and `CredReadW` for exactly the two named
generic credentials. It never enumerates, writes, rotates, updates, or deletes.
There is no environment, `.env`, file, command-line, or other fallback.

The executing SID must equal `owner_account_sid` before the first read. Both
entries must have the exact target, generic type, local-machine persistence,
nonempty strict UTF-8 value, and the approved bound. Missing, malformed,
empty, oversized, wrong-type, wrong-persistence, or inconsistent entries fail
closed.

Native writable copies are cleared and the entire native credential blob range
reported by `CredentialBlobSize` is cleared before `CredFree`, including an
oversized blob rejected by the application bound. The child copies at most the
approved application bound and retains the original native size only for
cleanup. Pointer/size validation, one-time release state, and cleanup on
success, rejection, decoding failure, validation failure, and exceptions keep
native cleanup fail-closed. Scoped Python objects redact `repr` and `str` and
drop references on close. Python immutable-string storage cannot be
guaranteed to be zeroized; this is a language-runtime limitation, not a
secret-lifetime claim. All credential exceptions are stable and sanitized.
Non-Windows construction fails closed.

## Child execution and one-call fence

The child performs this fixed sequence:

```text
strict child-request load
-> exact allocation load and evidence verification
-> exact credential-reference and capture-config verification
-> full reconciliation
-> exact current-process SID verification
-> two child-only Credential Manager reads
-> private two-key provider mapping
-> one provider instance
-> one-call provider fence
-> existing response acceptance and snapshot construction
-> canonical serialization and in-memory verification
-> existing staged no-clobber publication
-> independent final snapshot verification
-> canonical child-result publication
-> scoped-reference cleanup
```

The private mapping contains only `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY`, is passed directly to the existing provider factory, and
never enters `os.environ`. The fence marks entry before delegating and rejects
any second `fetch` before transport. There is no retry, fallback feed,
alternate endpoint, pagination continuation, reconnect, or second provider.

## Child result

`IsolatedCaptureChildResult` schema 1 binds exact child-request and allocation
evidence, attempt UUID, provider-call disposition, child classification,
ordered stable diagnostics, sanitized optional HTTP status/provider numeric
code/request ID, native exit code, optional snapshot evidence, snapshot
verification, secret cleanup, and child-operation version.

The closed classifications and dispositions are those in the implementation.
`SUCCEEDED` requires `RESPONSE_CONFIRMED`, native exit 0, cleanup `PASS`, and
an independently verified exact snapshot. A failed result cannot claim
snapshot verification `PASS`.

No result includes raw exception text, provider body, credential target
content, secret, environment dump, native handle, stdout, or stderr.

The UUID5 namespace is `b560a813-c0aa-50e7-ab5e-f6d21ef35f66`, with material
version `isolated-capture-child-result-v1`.

## Parent containment and environment

The parent refuses to start when either Alpaca variable exists in the parent
environment, including case variants. It verifies the exact child request,
approved Python executable bytes, approved script bytes, and absolute paths
before native creation. No credential API is imported into the launch flow and
no credential value crosses the process boundary.

The explicit child environment contains only:

```text
SystemRoot
WINDIR
TEMP=<controlled absolute directory>
TMP=<controlled absolute directory>
PYTHONUTF8=1
```

`PATH`, `PYTHONPATH`, proxies, certificate overrides, developer/Codex
variables, profiles, `HOME`, and all other parent entries are absent.
`PYTHONIOENCODING` is deliberately absent: with `bInheritHandles=false` the
approved Python runtime has no inherited standard handles, and the Windows
integration proves forced standard-stream encoding is not necessary.

The concrete adapter passes the approved executable as `lpApplicationName`,
uses an absolute script argument, never invokes a shell, and supplies a
Unicode environment block. It calls `CreateProcessW` with
`CREATE_SUSPENDED`, `bInheritHandles=false`, creates a Job Object, sets
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and active-process limit one, and assigns
the suspended child before evidence or resume.

The active-process limit makes redirecting virtual-environment launchers that
spawn a second base interpreter unsuitable. The approved executable must be a
non-redirecting Python runtime with the reviewed dependencies. The real
Windows integration uses the base runtime and proves suspended creation, Job
assignment, resume, exit-code capture, and handle cleanup.

## Process evidence and resume ordering

The immutable schema-1 records are:

- `ChildProcessCreationRecord`;
- `ChildResumeAuthorizationRecord`; and
- `ChildTerminationRecord`.

They bind allocation, child request, scheduled launch, approved executable and
release evidence, PID and native outcomes, handle posture, environment policy,
resume authorization, timeout/termination result, exit code, and stable
diagnostics as applicable. Each uses length-framed UUID5 material and strict
canonical JSON.

The creation record is published and canonically reread after Job assignment.
The resume-authorization record is then published and reread. Only then may
`ResumeThread` run. Creation or evidence failure keeps the child suspended and
attempts bounded process termination. Every owned process, primary-thread, and
Job handle is closed.

These records can be consumed by a later terminal or zero-call-proof milestone,
but they do not themselves prove that no provider call occurred.

## Timeout and ambiguity

The launcher waits the request's wall timeout, 30 seconds by default. On
timeout it calls `TerminateJobObject`, waits one additional bounded grace
interval, and distinguishes confirmed process-tree termination from
`PROCESS_TREE_TERMINATION_UNCONFIRMED`.

Timeout after resume is ambiguous: a provider call may have started.
Termination is not zero-call proof, does not authorize same-attempt reuse, and
does not authorize a retry. A parent crash after resume is likewise ambiguous.

Stdout and stderr are non-authoritative and never persisted or included in an
error/result. The injected process boundary bounds any supplied captured
stream at 64 KiB and records only stable overflow diagnostics. The concrete
no-inheritance adapter supplies no child standard handles, so its captured
streams are empty.

## CLI

```text
python scripts/run_isolated_capture_child.py --request <absolute-request.json>
python scripts/launch_isolated_capture_child.py --config <launcher-config.json>
```

Arguments and launcher configuration are nonsecret. Both commands use stable,
sanitized output and exit codes. Neither command allocates, advances, selects,
locks the production launch mutex, schedules, or invokes paper operation.
