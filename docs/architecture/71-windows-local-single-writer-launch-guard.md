# Windows local single-writer launch guard

## Milestone-C boundary

Milestone C implements only the Windows, one-machine, one-filesystem
single-writer prerequisite for later unattended simulated-paper work. It does
not schedule or wait for a session, invoke Task Scheduler, capture market data,
read credentials, evaluate readiness, execute a paper operation, publish a
receipt, advance the lineage head, retry, notify, launch a child process, or run
a daemon or background loop.

The guard is authority-wide. Capture and operation phases for one authority
epoch use the same mutex:

```text
Global\AITradingBot.PaperAuthority.<authority-epoch-id>
```

This prevents capture and operation authority from overlapping locally. The
kernel mutex is the active exclusion authority. Lease files are audit evidence
only and never grant, transfer, extend, recover, or revoke ownership.

## Native mutex contract

The narrow Windows adapter uses only `CreateMutexW`, `WaitForSingleObject`,
`ReleaseMutex`, `CloseHandle`, and the Win32 last-error value. Acquisition has
one explicit integer timeout and never requests `INFINITE`, sleeps, polls, or
deletes old evidence.

Every outcome is classified:

| Classification | Meaning |
| --- | --- |
| `ACQUIRED` | The calling thread owns the mutex. |
| `ALREADY_HELD` | The bounded wait expired without ownership. |
| `ABANDONED_ACQUIRED` | Windows transferred ownership after an owner terminated. |
| `ACCESS_DENIED` | Windows rejected access. |
| `UNSUPPORTED` | The platform or required ACL posture is unavailable. |
| `ERROR` | Another native or evidence error occurred. |

Only `ACQUIRED` and `ABANDONED_ACQUIRED` carry a private native handle.
The scoped ownership object does not expose or serialize that handle. It
releases at most once, closes the handle, rejects reuse after release, and can
be used as a context manager only when its release evidence was supplied
before entering the scope.

The mutex is thread-owned under Windows semantics. Callers must release it from
the acquiring thread. There is no force-unlock API, PID takeover, stale timeout,
lease renewal, or fallback file lock.

## Abandoned ownership

`WAIT_ABANDONED` means the mutex is acquired, but the prior protected operation
may have ended between state changes. The implementation publishes a start
record whose acquisition classification is `ABANDONED_ACQUIRED`, returns an
explicit manual-review diagnostic, and permits only release/audit handling.
No paper-domain action is authorized. Age, PID liveness, boot evidence, or a
missing release record cannot downgrade this result to a normal acquisition.

## Canonical lease evidence

Lease artifacts are frozen schema-1 models with compact, sorted, ASCII JSON and
one final newline. Parsing rejects BOMs, duplicate, missing, or unknown
members, floats, nonstandard constants, noncanonical UUID/hash/timestamp text,
and bytes that differ from canonical reserialization. All timestamps,
monotonic duration, process evidence, result evidence, and policies are
explicit caller inputs. No identity or constructor reads a clock, environment
variable, hostname, filesystem path, or native handle.

Lease-start identity uses namespace
`3785d749-91e1-5b48-995f-1e48708a209d` and material version
`launch-lease-start/v1`. It binds:

- scheduled launch, authority epoch, and scheduled phase;
- exact mutex name and acquisition classification;
- machine authority UUID and explicit boot evidence;
- PID, canonical process-creation timestamp, and canonical user SID;
- exact executable-release artifact evidence;
- canonical acquisition timestamp, maximum runtime, and launch policy.

Lease-release identity uses namespace
`7a154905-0644-5c08-8d04-d0a16c50d1cd` and material version
`launch-lease-release/v1`. It binds the exact content reference to the start
record, scheduled launch and authority epoch, release classification,
canonical release timestamp, exact monotonic duration in nanoseconds,
sanitized result classification and diagnostic, optional signed process exit
code, and release policy.

Both identities are UUID5 over versioned UTF-8 byte-length-framed material.
Paths and serialized bytes do not enter the UUID material. The release record
nevertheless contains the start record's exact UUID, SHA-256, and byte length,
so release evidence cannot be silently rebound to different start bytes.

## Publication and ordering

Artifacts are published below an existing safe output root:

```text
lock-events/launch-lease-start-<record-id>.json
lock-events/launch-lease-release-<release-id>.json
```

The publisher reuses the public safe-parent validator and independently
enforces a real `lock-events` directory, case-fold collision checks, regular
non-reparse entries, fixed filenames, bounded enumeration and rereads,
exclusive staging creation, flushed and fsynced staging bytes, identity-stable
parent checks, same-parent hard-link no-clobber finalization, and verified final
bytes. An existing final artifact is accepted only when its bytes are exactly
identical and canonical. Conflicts and unexpected entries fail closed.

The invocation-owned staging link is removed only after the exact final hard
link has been reread and verified. Any staging entry left by a crash or any
failure before that point is preserved for manual review. The implementation
does not overwrite, repair, prune, rename, or delete prior evidence.

Acquisition order is fixed:

```text
validate explicit inputs and safe root
→ acquire named mutex with bounded timeout
→ construct lease-start record
→ publish and reread lease-start record
→ return scoped ownership
```

If construction or start publication fails after native acquisition, the code
immediately attempts `ReleaseMutex` and `CloseHandle` and returns `ERROR`.

Release order is fixed:

```text
construct lease-release record
→ publish and reread lease-release record
→ ReleaseMutex
→ CloseHandle
```

Release is still attempted if evidence publication fails. Evidence or native
release failure is surfaced as an operational failure requiring manual review;
it is never converted into success.

## ACL and threat model

Verified mutex ACL construction and inspection are `NOT_IMPLEMENTED`.
`REQUIRE_VERIFIED_DACL` therefore returns `UNSUPPORTED` before any native
acquisition. `ALLOW_DEFAULT_DACL` is an explicit operator choice and reports
the same `NOT_IMPLEMENTED` enforcement status; it makes no claim about
hardening the process-token default DACL.

The version-one guarantee is local accidental-concurrency exclusion among
cooperating processes able to open the same Windows global mutex. It is not a
security boundary against another same-user process, an administrator, malware,
debugger injection, process termination, filesystem tampering, privilege
changes, or a second host. `Global\` namespace availability and access remain
subject to Windows session, token, policy, and DACL rules. `ACCESS_DENIED` and
unsupported ACL requirements fail closed.

## Read-only diagnostics

Diagnostics may expose only sanitized mutex name, PID, process-creation
timestamp, boot evidence, SID, lease-start reference, and released state.
They are read-only observations. Diagnostics do not inspect or terminate a
process, release a mutex, modify lease evidence, choose account state, or
authorize a domain action.

## CLI smoke boundary

`scripts/test_windows_launch_guard.py` is a foreground smoke command. It accepts
only explicit authority, launch, phase, machine, boot, PID/process-creation,
SID, executable-release, acquisition-time, runtime, timeout, policy, safe
output-root, ACL posture, and release-evidence inputs. It acquires the mutex,
publishes start evidence, immediately publishes the supplied release evidence,
and releases. An abandoned acquisition is released without any domain call and
returns a distinct nonzero status.

Example:

```text
python scripts/test_windows_launch_guard.py \
  --authority-epoch-id 8a39e78a-47d8-50b9-a427-c102abc91e1e \
  --scheduled-launch-id 89a3184a-05ef-5228-8664-d26f31ed03c9 \
  --phase OPERATION \
  --machine-authority-id 71abfbb7-ae72-54fc-b049-3ea87879dd32 \
  --boot-evidence boot-2026-07-30T00:00:00Z \
  --process-id 4242 \
  --process-creation-timestamp 2026-07-30T16:00:00Z \
  --user-sid S-1-5-21-111-222-333-1001 \
  --executable-release-id 918a8cd2-b8fd-5334-8df3-b62eab72e311 \
  --executable-release-sha256 7777777777777777777777777777777777777777777777777777777777777777 \
  --executable-release-byte-length 1200 \
  --acquisition-timestamp 2026-07-30T16:00:01Z \
  --max-runtime-seconds 900 \
  --timeout-seconds 3 \
  --policy windows-local-single-writer-v1 \
  --output-root C:\paper-authority-audit \
  --release-evidence-input C:\reviewed\release-evidence.json \
  --acl-policy ALLOW_DEFAULT_DACL
```

The release-evidence input is a bounded JSON object with exact members:
`release_classification`, `release_timestamp_utc`,
`monotonic_duration_nanoseconds`, `result_classification`,
`result_diagnostic`, nullable `process_exit_code`, and `release_policy`.
Because this smoke path never invokes a domain operation, it accepts only
`result_classification: NOT_RUN`.
