# Guarded capture-readiness dry-run

## Milestone-D boundary

Milestone D is a one-shot foreground runner that proves whether the next
scheduled daily market-data capture attempt would be allowed from explicit
evidence while the authority-wide Windows mutex is held.

It never imports or calls a market-data provider, reads credentials, creates a
snapshot, allocates an attempt record, runs a paper operation, recovers a
receipt, advances the lineage head, generates a target or strategy, contacts a
broker or network service, installs a task, waits, retries, repairs, cleans up
prior evidence, or starts a daemon, service, poller, child process, or
background loop. `provider_invocation_permitted` is evidence only.

This milestone does not approve provider capture or unattended scheduling. A
later capture adapter must consume a verified `READY` decision as one gate and
requires separate approval.

## Strict configuration schema

`GuardedCaptureReadinessConfig` schema 1 contains exactly:

```text
schema_version
authority_root
authority_epoch_id
scheduler_audit_root
scheduled_phase
target_session
execution_session
symbols
universe_policy_version
readiness_policy_version
selection_policy_version
nominal_scheduled_slot
launch_retry_ordinal
observed_current_utc_timestamp
acquisition_timestamp_utc
release_timestamp_utc
monotonic_duration_nanoseconds
machine_authority_id
boot_session_evidence
process_id
process_creation_timestamp_utc
account_sid
executable_release_evidence
maximum_runtime_seconds
mutex_timeout_seconds
launch_guard_policy_version
acl_mode
market_hours_schedule_artifact
capture_policy_artifact
capture_attempt_artifacts
snapshot_selection_artifact
manual_disable_active
capture_health
runner_policy_version
```

`scheduled_phase` is fixed to `CAPTURE_READINESS_DRY_RUN`.
`capture_health` contains exactly `audit_ok`, `disk_watermark_ok`, `backup_ok`,
and `notification_ok`. `executable_release_evidence` contains an artifact UUID,
SHA-256, and byte length. Each referenced input artifact adds an explicit path
to those evidence fields. Attempt references retain caller order and selection
is nullable.

The ordered symbols and universe/readiness policy versions are explicit in the
config because session and launch identities must be derived before a
referenced artifact is opened. After acquisition, the verified capture policy
must contain the same ordered universe.

Paths are transport metadata and do not enter scheduled-session, launch,
attempt, or decision identities. The loader accepts bounded strict UTF-8 JSON
only. It rejects BOMs, duplicate, missing, or unknown members, floats,
nonstandard constants, and noncanonical UUID, SHA-256, UTC timestamp, date,
enum, symbol, SID, policy, and bounded-integer values.

## Explicit time boundary

The runner reads neither the system clock nor a monotonic clock. Nominal slot,
observed time, mutex acquisition time, process creation time, release time, and
monotonic duration are explicit inputs.

A later production adapter must obtain these values from approved operating
system sources and validate their chronology and trust boundary. This
milestone does not treat a human-authored timestamp as a trusted observation.

## Orchestration and mutex ordering

The exact successful order is:

```text
strict config load
-> scheduled session and launch identity derivation
-> authority-wide Windows mutex acquisition
-> scheduler audit-root validation
-> lease-start publication and canonical reread
-> current authoritative lineage-head verification
-> market-hours and capture-policy verification
-> ordered attempt and optional selection verification
-> pure scheduled capture-readiness evaluation
-> canonical decision construction
-> decision publication and canonical reread
-> lease-release publication with sanitized result
-> ReleaseMutex and CloseHandle
-> deterministic CLI result
```

No referenced artifact, authority pointer, readiness input, or output directory
is opened before native acquisition. Existing guard callers retain default
pre-acquisition audit validation; this runner explicitly selects deferred audit
validation. Deferred validation or lease-start failure attempts native release
and close and prevents readiness work.

After start publication, release evidence and native release are attempted on
every runner-controlled path for either normal or abandoned acquisition.
Release publication occurs before `ReleaseMutex`; native release is attempted
even when release publication fails.

Guard behavior is:

| Guard outcome | Dry-run classification | Behavior |
| --- | --- | --- |
| `ACQUIRED` | evaluator result | Continue after verified lease start. |
| `ALREADY_HELD` | `NOT_READY` | `GUARD_ALREADY_HELD`; no readiness or filesystem work. |
| `ABANDONED_ACQUIRED` | `MANUAL_REVIEW_REQUIRED` | Publish start/release; do not call the evaluator. |
| `ACCESS_DENIED` | `BLOCKED` | `GUARD_ACCESS_DENIED`; fail closed. |
| `UNSUPPORTED` | `BLOCKED` | `GUARD_UNSUPPORTED`; fail closed. |
| `ERROR` | `BLOCKED` | Stable guard or lease-start diagnostic. |

The orchestration diagnostics are:

```text
GUARD_ALREADY_HELD
GUARD_ABANDONED
GUARD_ACCESS_DENIED
GUARD_UNSUPPORTED
GUARD_ERROR
LEASE_START_PUBLICATION_FAILED
HEAD_VERIFICATION_FAILED
HOURS_ARTIFACT_INVALID
CAPTURE_POLICY_INVALID
ATTEMPT_HISTORY_INVALID
READINESS_EVALUATION_FAILED
DECISION_PUBLICATION_FAILED
LEASE_RELEASE_PUBLICATION_FAILED
MUTEX_RELEASE_FAILED
```

`CONFIGURATION_INVALID` is the stable CLI diagnostic for a failure before IDs
can be safely derived.

## Verified inputs and pure capture readiness

The current pointer-selected lineage is verified completely with the
milestone-69 API and normalized with the existing readiness adapter. The
configured epoch must equal the verified current epoch.

Market-hours and capture-policy files are canonical schema-1 artifacts. Their
configured hash and length are checked before parsing. Attempt and selection
artifacts also require configured artifact UUID and full evidence to equal the
canonical record evidence.

`evaluate_scheduled_capture_readiness` is the capture-only pure view of
milestone 70. It reuses snapshot window, backoff, exhaustion, terminal
chronology, selection, attempt-conflict, health, manual-disable, session, and
scheduled-identity rules without operation, target, receipt, or coordinator
gates.

- Open first-attempt or retry windows are `READY`.
- Too early, active backoff, or an eligible snapshot awaiting selection is
  `NOT_READY`.
- A valid selected snapshot is `ALREADY_COMPLETED`.
- Expiry, exhaustion, manual disable, invalid sessions, or unhealthy capture
  gates are `BLOCKED`.
- Attempt or selection conflicts are `CONFLICTING`.

Only `READY` yields `CAPTURE_ATTEMPT_ALLOWED`,
`provider_invocation_permitted: true`, the next contiguous ordinal, and its
deterministic attempt UUID. The attempt is not allocated or published.
`NOT_READY` yields `WAIT`; manual review yields `MANUAL_REVIEW`; other results
yield `NONE`.

## Immutable decision evidence and identity

`ScheduledCaptureReadinessDecision` schema 1 contains exactly:

```text
schema_version
decision_id
scheduled_session_id
scheduled_launch_id
authority_epoch_id
lease_start
head_record
terminal_checkpoint
market_hours_schedule
capture_policy
capture_attempts
snapshot_selection
observed_at
readiness_classification
diagnostics
provider_invocation_permitted
next_eligible_action
capture_attempt_ordinal
capture_attempt_id
runner_policy_version
```

The UUID5 namespace is `8dc35263-331b-55c9-946d-1f3747fd43b5`; material
version is `scheduled-capture-readiness-decision-v1`. Versioned UTF-8
byte-length-framed material binds every semantic field, ordered attempt
evidence, ordered diagnostics, and explicit nullable markers. Paths and native
mutex handles are excluded.

Canonical JSON is compact, sorted, ASCII-safe UTF-8 with one final newline.
Parsing recomputes the decision UUID and rejects noncanonical bytes. Identical
explicit inputs produce the same ID and exact bytes. Changed observed time
changes the decision identity. Changed launch retry ordinal changes the launch
and downstream decision identity, matching the milestone-70 identity boundary.

## Decision publication

The fixed layout is:

```text
<scheduler-audit-root>/
  readiness-decisions/
    scheduled-capture-readiness-decision-<decision-id>.json
```

The audit root must already be safe. The publisher creates only the fixed child
directory. It rejects links, reparse points, case-fold collisions, unexpected
entries, unstable parent/file identities, excessive enumeration, oversized
rereads, and noncanonical existing artifacts.

Publication uses exclusive same-parent staging, write and file `fsync`, bounded
canonical reread, no-clobber hard-link finalization, and exact final reread.
Identical existing bytes are idempotent; conflicting bytes fail closed.
Crash-left staging is preserved and blocks publication. No prior evidence is
overwritten, repaired, or cleaned.

## CLI and exit behavior

```text
python scripts/evaluate_guarded_capture_readiness.py --config <strict-config.json>
```

The compact JSON output contains only scheduled session and launch IDs;
lease-start ID when acquired; readiness classification; diagnostics; next
action; proposed attempt ordinal and UUID when allowed; decision UUID and path
when published; and lease-release UUID when published.

| Code | Meaning |
| --- | --- |
| `0` | Verified `READY`, `NOT_READY`, or `ALREADY_COMPLETED` decision evidence. |
| `2` | Usage. |
| `4` | Input/head/hours/policy/attempt/readiness failure or other blocked result. |
| `5` | `CONFLICTING`. |
| `7` | Audit publication, guard operational, or native release failure. |
| `8` | `MANUAL_REVIEW_REQUIRED`, including abandoned ownership. |
| `9` | Guard already held. |
| `10` | Unsupported or access-denied guard state. |

## Windows, ACL, and scheduling limitations

The authority-wide mutex remains
`Global\AITradingBot.PaperAuthority.<authority-epoch-id>`. It is thread-owned
and released by the acquiring foreground thread. There is no file-lock
fallback, stale-lock deletion, force unlock, renewal, takeover, or multi-host
coordination.

`REQUIRE_VERIFIED_DACL` remains `UNSUPPORTED`. `ALLOW_DEFAULT_DACL` explicitly
accepts enforcement status `NOT_IMPLEMENTED`; the mutex is an accidental local
concurrency boundary, not a security boundary.

The runner has no Task Scheduler dependency and creates no XML or installation
state.
