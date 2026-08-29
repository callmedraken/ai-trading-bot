# Windows production effectful market-data capture validation plan

## 1. Purpose and evidence standard

This plan validates the C3 contract in
`docs/architecture/82-windows-production-effectful-market-data-capture.md`.

C3 is not considered complete because an Alpaca request succeeds. The evidence
must establish the complete authority chain from C1 production validation,
through C2 durable intent and recovery fences, through the real Windows child
boundary, to independent parent verification and C2 selection of one exact
canonical snapshot artifact.

The plan intentionally tests interactions and crash windows rather than only
isolated methods. Every effectful boundary must prove:

```text
durable C2 authority
-> effect with no SQLite transaction active
-> exact typed/process-local result
-> verified durable result or conservative recovery
```

The following are invalid evidence of success by themselves:

- child exit code zero;
- child `SUCCEEDED` classification;
- an output filename;
- a child-reported digest;
- a valid-looking orphaned artifact found after restart;
- a PID/process handle;
- a raw provider response;
- a manually supplied 32-byte snapshot digest.

Production SQL is expected to remain unchanged. Any proposed schema migration
requires a separate architecture review showing that the C3 contract cannot be
represented by the existing C2 model.

## 2. Validation layers

The C3 test program has five layers:

1. deterministic pure contract tests;
2. injected fake/native boundary tests;
3. C1/C2/C3 integration tests using non-network fakes;
4. real Windows process/credential containment acceptance;
5. one controlled real Alpaca market-data acceptance invocation.

Brokerage credentials, brokerage APIs, paper-account mutation, and real-money
orders are prohibited in every layer.

## 3. Contract and canonical-encoding gate

Create strict tests for every new C3 immutable value, including at least:

- production capture plan;
- authorized-snapshot bridge result;
- nonsecret provider launch plan;
- child request;
- child result;
- native cleanup evidence;
- terminal diagnostic evidence;
- verified final artifact evidence;
- process-local `VerifiedCapturedSnapshot` authorization.

For every serialized v1 object, table-driven tests reject:

- duplicate keys;
- missing keys;
- unknown keys;
- wrong exact scalar types;
- floats and non-finite constants;
- noncanonical UUID/hash/date/timestamp text;
- invalid UTF-8 or BOM where byte serialization applies;
- oversized payloads;
- trailing data;
- alternate provider/operation values;
- alternate protocol/policy versions;
- caller-selected credential names;
- caller-selected executable/output paths where prohibited.

Canonical round-trip bytes and deterministic identity vectors are frozen before
native implementation. Reordering dictionary construction or changing runtime
clock/PID/path must not change identity material unless the architecture
explicitly declares that fact semantic.

## 4. C2 request to snapshot-session bridge gate

The bridge suite varies:

- request-window start/end dates;
- target session date;
- weekdays;
- weekends;
- XNYS holidays represented by the current identified calendar;
- multi-day windows;
- windows containing exactly one session;
- windows containing no session;
- runtime `requested_at_utc` values before/after New York date boundaries;
- ordered universe;
- calendar/provider descriptor mismatches.

For every accepted case the test proves exactly:

```text
authorized_snapshot_session =
    latest modeled XNYS session within the inclusive request window
```

and requires:

```text
authorized_snapshot_session < target_session_date
existing daily-snapshot completed-session derivation(requested_at_utc)
    == authorized_snapshot_session
```

A mismatch fails before the C3 provider-attempt fence and before a real provider
is constructed.

Tests also prove the derived daily-snapshot request UUID is deterministic and
bound to the exact C2 lineage/material rather than caller randomness.

The existing daily-snapshot identity, acceptance, serialization, replay, and
offline-verification suites must remain green and are not replaced by C3 tests.

## 5. Production composition gate

C3 composition tests prove:

- bare production `WindowsTransactionalAuthority` remains effectfully inert;
- only the C3 production facade supplies the reviewed external adapter;
- callers cannot supply a production adapter instance;
- callers cannot supply Credential Manager target names;
- callers cannot supply the output root or final filename;
- callers cannot inject a provider implementation, endpoint, executable, child
  entrypoint, Job Object policy, or native process flags;
- callers cannot directly inject successful `snapshot_digest` authority.

The test observes the exact high-level ordering:

```text
C1 validation
-> C2 session
-> attempt
-> permanent claim
-> launch reservation
-> nonsecret provider-plan construction
-> process intent commit
-> native process effect
-> process-result commit
-> resume intent commit
-> resume effect
-> child/result observation and cleanup
-> C2 post-resume/cleanup persistence
-> parent artifact verification/publication
-> C2 successful/failed/ambiguous terminal
-> selection where allowed
```

No external effect may occur while any C3-used SQLite connection is in a
transaction.

## 6. Provider-plan construction gate

Injected tests prove C2 `construct_provider` in C3 means nonsecret launch-plan
construction only.

It must reject before plan issuance when any of these disagree with the active
reservation lineage:

- C2 request digest;
- provider ID;
- permitted operation;
- authorized snapshot session;
- child operation version;
- credential-policy version;
- output-policy version;
- release binding.

Successful provider-plan construction must not:

- call Credential Manager;
- create the Alpaca HTTP provider in the parent;
- open network transport;
- create a process;
- create a final artifact;
- mutate C2 beyond the documented surrounding workflow.

Lost/reconstructed/copied plan capabilities do not authorize a second
construction or later process intent.

## 7. Windows Credential Manager unit gate

Use an injected native API to cover at least:

- exact Trading SID;
- wrong SID;
- SID inspection failure;
- missing API-key entry;
- missing secret entry;
- wrong target returned by native adapter;
- wrong credential type;
- wrong persistence;
- empty credential;
- leading/trailing whitespace;
- CR/LF/NUL;
- invalid UTF-8;
- application-copy bound exceeded;
- native maximum valid blob size;
- invalid pointer/size combination;
- zero-size/null behavior;
- native clear failure;
- `CredFree` failure;
- exception while decoding first credential;
- exception while reading/decoding second credential;
- double release/close.

Every case proves:

- credential read does not occur before SID verification;
- only the two exact target names are read;
- no enumeration/write/delete API is used;
- no environment/file fallback exists;
- native release is attempted exactly once for every acquired native entry;
- valid native buffer ranges are cleared before release where required;
- secret-bearing representations are redacted;
- stable raised errors contain no credential content.

Python immutable-string zeroization is not asserted.

## 8. Parent secret-isolation gate

Instrumentation around the production parent proves that no credential value is
present in:

- parent environment;
- process command line;
- child request bytes;
- SQLite evidence;
- logs/diagnostics;
- final artifact;
- child result;
- process/Job/resume evidence;
- exception text returned to the operator.

The parent must not import or invoke the credential read boundary on the normal
production path except for code-definition/import relationships that do not
materialize credential data.

## 9. Child request and bounded-transport gate

The request channel is tested for:

- exact canonical valid request;
- zero-length request;
- truncation;
- over-limit request;
- partial reads;
- duplicate/unknown fields;
- wrong reservation/execution/release binding;
- alternate credential policy;
- alternate provider;
- alternate authorized session;
- premature channel close.

Invalid child input cannot enter Credential Manager or provider transport.

The child never treats numeric inherited handle values, a PID, or a command-line
path as semantic authority.

## 10. One-attempt provider fence gate

An injected provider and transport count every attempted `fetch`/HTTP operation.

All success and failure paths require:

```text
provider fetch count <= 1
HTTP request count <= 1
```

Test failures before and after the logical `C3_PROVIDER_ATTEMPT_ENTERED` fence.
Once entered:

- a credential failure does not authorize another attempt;
- a provider-construction failure does not authorize another attempt;
- a transport failure does not authorize another attempt;
- malformed response does not authorize another attempt;
- snapshot rejection does not authorize another attempt;
- serialization/staging failure does not authorize another attempt.

There is no hidden retry, reconnect, pagination continuation issuing another
provider call, fallback feed, alternate endpoint, or provider replacement.

A second attempted entry into the fence is rejected before provider transport.

## 11. Child-result gate

For each allowed child classification, tests construct the minimum valid
canonical result and reject contradictory combinations.

Examples:

- `SUCCEEDED` requires a claimed snapshot identity/hash/length and successful
  child cleanup classification;
- failure cannot claim parent verification success;
- classifications requiring provider-attempt entry cannot claim the fence was
  never entered;
- pre-fence request rejection cannot claim an HTTP/provider result;
- malformed/unknown classifications fail closed.

The parser rejects raw exception strings, raw provider bodies, arbitrary nested
objects, unexpected path material, and over-limit output.

Child result alone cannot issue `VerifiedCapturedSnapshot` or a C2 successful
terminal.

## 12. Job Object configuration gate

An injected Win32 adapter records exact native call ordering.

The expected preparation order includes:

```text
CreateJobObject
-> SetInformationJobObject(KILL_ON_JOB_CLOSE + ACTIVE_PROCESS=1)
-> prepare bounded request/result/staging handles
-> InitializeProcThreadAttributeList
-> UpdateProcThreadAttribute(HANDLE_LIST)
-> UpdateProcThreadAttribute(JOB_LIST)
-> optional reviewed CHILD_PROCESS_POLICY
-> CreateProcessW(CREATE_SUSPENDED + reviewed flags)
```

The successful C3 path must not depend on a later
`AssignProcessToJobObject` call.

Tests reject:

- missing KILL_ON_JOB_CLOSE;
- active-process limit other than one;
- breakaway flags;
- missing JOB_LIST;
- missing HANDLE_LIST;
- caller-added handle;
- `lpApplicationName=NULL`;
- relative executable;
- shell launch;
- missing `EXTENDED_STARTUPINFO_PRESENT`;
- process created nonsuspended;
- inherited parent environment.

## 13. Handle-inheritance gate

C3 uses `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` with `bInheritHandles=TRUE`.

Fake and real tests create additional deliberately inheritable sentinel handles.
The child must receive only:

- request read handle;
- result write handle;
- staging write handle.

The child must not inherit the sentinel or any authority-database/lifecycle
handle exposed by the test harness.

Each parent and child pipe endpoint has an explicit owner. Unused opposite ends
are closed at the earliest safe point so EOF/pipe completion cannot be masked by
an accidentally retained duplicate handle.

## 14. Process-creation result gate

A successful typed process receipt may be issued only after the adapter proves
all C3 pre-resume requirements.

Tests inject failure at every native preparation/creation step and verify:

- no success receipt before full suspended creation/Job assignment evidence;
- definitive `NOT_CREATED` only when no child can exist;
- uncertain process-creation states do not fabricate definitive failure;
- process intent is consumed at most once;
- result is exact-reservation/process-intent bound;
- copied/reconstructed/mutated/wrong-reservation/reused results fail before C2
  persistence;
- every acquired native resource receives its required cleanup attempt.

Existing C2 provenance/one-shot tests remain part of the affected regression
set.

## 15. Process-local registry gate

The private live-handle registry is tested for:

- exact reservation/execution binding;
- duplicate registration rejection;
- stale lookup rejection;
- reflective mutation of caller-visible fields not redirecting registry-owned
  identity;
- release/removal after terminal cleanup;
- no serialization/pickling;
- no reconstruction from PID or durable C2 rows;
- no live entry surviving simulated process restart.

A stale live object after durable C2 revocation cannot perform resume, wait,
persist, or artifact authorization.

## 16. Resume gate

Tests prove:

```text
C2 ResumeIntent commits before ResumeThread
ResumeThread is called exactly once
exact primary-thread handle is used
successful previous suspend count == 1
```

Cases include:

- normal return 1;
- failure return `(DWORD)-1`;
- unexpected return 0;
- unexpected return >1;
- native exception;
- second resume attempt;
- recovery wins before resume;
- resume wins before recovery;
- delayed resume after C2 revocation.

No unexpected return authorizes a second `ResumeThread` call.

Inter-process tests force recovery-vs-resume orderings with deterministic events,
not sleeps.

## 17. Post-resume wait/timeout/termination gate

Injected cases include:

- normal child exit zero;
- normal child exit nonzero;
- child result before exit;
- exit before complete result;
- timeout;
- `TerminateJobObject` success;
- termination wait success;
- termination wait timeout/failure;
- process wait failure;
- exit-code query failure;
- result pipe closes early;
- result exceeds bound;
- result is malformed;
- staging writer closes early;
- cleanup of one handle fails while remaining cleanup continues;
- Job Object close failure/diagnostic path.

The classification is deterministic and sanitized.

Timeout or termination after resume never proves zero provider attempts and
never authorizes retry.

## 18. Real cleanup-evidence gate

C3 constructs canonical cleanup evidence only from reviewed safe
classifications. It does not persist raw HANDLE values, raw Win32 messages, raw
exception text, environment data, or credential/provider bodies.

Tests prove the additive C2 production-evidence seam:

- accepts exact C3-issued cleanup evidence for the correct execution;
- rejects direct/copy/reconstructed/wrong-execution evidence;
- checks bytes/digest exactly;
- persists the existing `post_resume_json/digest` and `cleanup_json/digest`
  columns without schema change;
- preserves existing phase/state predicates;
- consumes one-shot authority only after commit where applicable;
- preserves the existing deterministic test-seam behavior outside production
  C3 composition.

Injected SQLite rollback preserves a still-active exact result only when the
existing C2 contract permits retry of persistence; C3 external effects are not
repeated.

## 19. Parent-owned staging gate

The parent staging boundary is tested for:

- fixed C1 output root only;
- deterministic bounded staging name;
- exclusive create;
- pre-existing exact collision;
- case-fold collision on Windows;
- reparse/symlink/junction substitution according to C1 path policy;
- child receives only the exact write handle;
- caller cannot substitute a destination;
- staged object identity retained across child execution;
- cleanup attempts only on the invocation-owned staging identity.

A changed or substituted staging identity fails closed and is not blindly
deleted.

## 20. Parent-independent artifact verification gate

After child completion, malicious test cases vary the staged bytes by:

- truncation;
- appended bytes;
- noncanonical JSON;
- invalid UTF-8;
- wrong snapshot UUID;
- wrong capture request;
- wrong requested-at/session relationship;
- wrong target session;
- wrong symbol set/order;
- wrong provider descriptor;
- wrong source/audit evidence;
- wrong claimed SHA-256;
- wrong claimed byte length;
- child-result mismatch;
- stale/future/mixed-session bars;
- replacement between reads;
- final-object collision.

None may issue `VerifiedCapturedSnapshot`.

Accepted bytes must pass the existing offline verifier and exact C3/C2
reconciliation. The final no-clobber artifact is independently reopened and
reverified after publication.

## 21. `VerifiedCapturedSnapshot` provenance gate

Tests prove:

- direct construction is unavailable;
- copy/pickle/serialization is unavailable;
- wrong service/issuer fails;
- wrong reservation/execution fails;
- public-field reflective mutation cannot redirect registry-side binding;
- stale capability after terminal/recovery/close fails;
- exact live capability authorizes success once;
- reuse fails;
- successful terminal digest equals SHA-256 of the exact final canonical
  artifact bytes;
- selection copies that exact digest.

The C3 public facade must not expose a successful-terminal method taking an
arbitrary `bytes` snapshot digest.

## 22. Terminal diagnostic-evidence gate

C3 issues stable sanitized terminal evidence/diagnostics for definitive failure,
ambiguity, and success.

The C2 production seam rejects:

- malformed canonical evidence;
- wrong digest;
- wrong reservation;
- raw exception/provider-body insertion;
- copied/reconstructed one-shot evidence where provenance is required;
- evidence delayed past terminal/recovery revocation.

The existing terminal state/disposition/snapshot matrix is unchanged.

## 23. Complete terminal-mapping gate

The suite exercises every allowed C3-to-C2 mapping:

| C3 condition | Required C2 result |
| --- | --- |
| definitive native process creation failure | `FAILED / NOT_STARTED`, no snapshot |
| process creation outcome uncertain | unknown-process recovery, no fabricated result |
| suspended persisted execution abandoned pre-resume | pre-resume recovery/manual review |
| resume outcome/restart uncertainty | unknown-resume recovery/manual review |
| current process knows resume occurred but child result remains unresolved | `AMBIGUOUS / MAY_HAVE_OCCURRED` |
| definitive post-fence child/provider failure | `FAILED / CONFIRMED` |
| definitive parent verification/publication failure after confirmed attempt | `FAILED / CONFIRMED` |
| exact parent-verified final artifact | `SUCCEEDED / CONFIRMED` with artifact SHA-256 |

Every disallowed state/disposition/snapshot combination must be rejected by the
existing C2/SQL gates.

## 24. Crash matrix

The test harness introduces deterministic interruption at every authority/effect
boundary.

| Crash/interruption point | Expected standing |
| --- | --- |
| before session/claim | no provider-call authority exists |
| after claim, before reservation | existing C2 durable claim semantics only |
| after reservation, before provider-plan construction | `CLASSIFY_LAUNCH_RESERVATION` after restart |
| after provider-plan construction, before process intent | no reconstruction/retry of provider-plan capability; classify reservation when lost |
| after process intent commit, before `CreateProcessW` | `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` |
| after native child creation, before process-result persistence | same unknown-process recovery |
| after definitive process-result persistence, before resume intent | `CLASSIFY_PRE_RESUME_READY` |
| after resume-intent commit, before `ResumeThread` | `CLASSIFY_RESUME_OUTCOME_UNKNOWN` after restart |
| immediately after `ResumeThread` | same unknown-resume recovery after restart |
| after provider-attempt fence, before child result | no automatic retry; ambiguity/manual review as durable state permits |
| after staging write, before parent verification | no snapshot authority |
| after parent verification capability issuance, before final publication | lost process-local capability is not reconstructed |
| after final publication, before success terminal | final file is historical evidence only after restart; no scan/promotion |
| after success terminal, before selection | existing committed-success selection recovery |
| after selection | completed C2 success |

Each case proves that restart does not recreate provider, process, resume, or
snapshot authorization from public/durable fields.

## 25. Concurrent recovery/effect race gate

For process dispatch, process-result persistence, resume dispatch, post-resume
persistence, and terminal authorization, deterministic tests force both orderings
against the same reservation lifecycle arbiter.

Recovery-first must revoke/delay the C3 effect or persistence without emitting a
new external effect.

Effect-first may leave a conservative unknown/ambiguous durable state when the
external outcome is not yet durably recorded, but it never permits the effect to
run twice.

No test uses scheduler timing or `sleep` as the authority for race ordering.

## 26. Artifact/recovery race gate

Tests deliberately race/sequence:

- parent verification vs durable recovery classification;
- final publication vs terminal recording;
- terminal success vs selection recovery;
- delayed verifier capability vs manual review/closure.

A verifier capability delayed past C2 revocation cannot authorize success even
when the artifact remains byte-for-byte valid.

A file never overrides a newer durable manual-review or terminal fact.

## 27. Real Windows process-containment acceptance

Run on the intended supported Windows version with the production-style Trading
account and reviewed installation layout.

Acceptance proves:

- C1 production validation succeeds first;
- exact Trading SID is observed in both parent authority and child;
- production `Global\\AITradingBot-Lifecycle-v1-<digest>` arbitration is used;
- Job Object is configured with KILL_ON_JOB_CLOSE and active-process limit one;
- `STARTUPINFOEXW` JOB_LIST assigns the child at creation;
- child is initially suspended;
- only the three intended handles are inherited;
- deliberately inheritable sentinel handles are absent in the child;
- child environment matches the reviewed allowlist;
- no shell/PATH lookup is involved;
- ResumeThread reports previous suspend count one;
- an attempted child descendant is rejected/contained according to the reviewed
  policy;
- closing/terminating the Job bounds the child tree;
- native handles are cleaned according to ownership rules.

Record only sanitized acceptance evidence. Do not persist raw secret values or
native HANDLE numbers as durable project evidence.

## 28. Real Windows Credential Manager acceptance

Provision the two exact generic credentials under the dedicated Trading account
using an administrator/operator workflow outside C3.

Acceptance proves:

- target names exactly match the C3 constants;
- type is generic;
- persistence is the supported local-machine value;
- child current SID equals the configured owner Trading SID;
- child can read both exact values;
- parent cannot observe the secret through the C3 interfaces;
- wrong-account execution fails before first credential read;
- a deliberately missing/invalid entry fails closed with sanitized evidence;
- cleanup/release completes without exposing secret material.

Credential content is never checked into the repository or copied into the
acceptance report.

## 29. Controlled real Alpaca acceptance

Only after the real Windows process and credential gates pass, run one manually
invoked C3 capture using market-data-only Alpaca credentials.

The acceptance invocation must prove:

- exact approved provider descriptor/operation;
- exactly one C2 permanent claim;
- exactly one C3 provider-attempt fence entry;
- at most one actual provider HTTP request;
- no parent credentials;
- child process is contained and resumed through C2 ordering;
- provider response passes existing bounded parsing/acceptance;
- child candidate bytes are independently verified by the parent;
- final artifact is published only in the C1 fixed output root;
- final artifact SHA-256 equals the C2 terminal snapshot digest;
- successful C2 terminal and selection bind that digest;
- no paper-account or broker operation occurs.

If provider availability prevents a successful snapshot, the run may still
produce useful failure evidence but does not satisfy the successful C3
end-to-end acceptance gate.

## 30. Restart and orphan-artifact native acceptance

At least one native/manual acceptance scenario must leave a valid-looking
artifact or staging object without a committed successful terminal, then restart
the program.

The restarted process must not:

- discover and promote the artifact;
- recreate `VerifiedCapturedSnapshot`;
- reissue provider/process/resume capability;
- silently retry the provider.

It must report/use the existing C2 conservative recovery corresponding to the
durable state.

## 31. Secret-leak audit

Before C3 completion, search the exact changed source/tests/docs and generated
acceptance outputs for:

- actual API key/secret values used during acceptance;
- `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` value logging;
- raw provider response bodies in diagnostics;
- environment dumps;
- traceback/raw exception persistence;
- credential target content beyond the approved constant names;
- accidental command-line credential transport.

The audit is a defense-in-depth check and is not a substitute for architectural
secret isolation.

## 32. Source-boundary audit

Review every executable call site for:

- `CredReadW` / Credential Manager access;
- provider construction;
- provider `fetch` / network transport;
- Job Object creation/configuration;
- `CreateProcessW`;
- `ResumeThread`;
- process wait/termination;
- final artifact publication;
- successful C2 terminal authorization.

Each call site must map to exactly one documented C3 boundary and must not have
an alternate production path that bypasses C1/C2/C3 composition.

## 33. No-schema-change gate

Before final certification:

- compare `src/trading_bot/runtime/schema/windows_transactional_authority_v1.sql`
  to the C2-certified artifact;
- require the production SQL byte length and SHA-256 to remain unchanged;
- rerun the affected Architecture-77/C2 schema/state suites.

If implementation discovers a genuine need for a schema change, stop C3,
document the conflicting requirement, and reopen architecture review rather
than silently migrating the authority database.

## 34. Static and focused certification gates

During implementation use focused suites for the current C3 sub-boundary.

Before declaring the integrated C3 tree reviewable, run at least:

- all C3 pure contract/bridge tests;
- C3 credential/child tests;
- C3 native-adapter fake tests;
- C3 artifact-verification tests;
- C3 integration/crash/race tests;
- affected C1 validation tests;
- affected C2 service and Architecture-77 transactional tests;
- Ruff check on changed/source test scope;
- Ruff format check;
- `git diff --check`;
- production SQL identity check.

Do not repeatedly run the entire repository suite after every intermediate C3
correction.

## 35. Deep pre-acceptance review

Once C3-A through C3-E are integrated, perform one dedicated deep review before
native acceptance. The review inventory must explicitly cover:

- secret isolation;
- C2-to-snapshot date/session mapping;
- one-attempt semantics;
- SQLite/lifecycle lock order;
- Job/handle containment;
- process-local registry lifetime;
- exactly-once native cleanup;
- C2 result provenance;
- artifact identity and parent verification;
- terminal/snapshot authorization;
- crash/restart behavior;
- recovery/effect races;
- absence of artifact discovery authority;
- absence of scheduling/brokerage scope creep.

Resolve that inventory as a set instead of submitting isolated rolling findings.

## 36. Final repository certification

Only after the exact C3 head is architecture-review clean and native Windows
acceptance is complete:

1. verify exact Git commit/head;
2. run the complete repository test suite once on that exact tree;
3. run final Ruff check/format check and `git diff --check`;
4. verify production SQL identity unchanged;
5. verify acceptance evidence references the exact release/source commit;
6. review the exact PR diff and any fresh GitHub review findings;
7. update the PR verification record;
8. report merge readiness without merging until explicitly approved.

## 37. C3 exit criterion

C3 passes only when deterministic tests plus native evidence support this exact
claim:

> From one exact C1-approved Trading process, one manually invoked nonsecret
> request can cause at most one C2-authorized provider attempt; secrets exist
> only inside the contained child; process creation and resume obey the durable
> C2 fences; every ambiguous crash fails closed without automatic retry; and
> only a parent-independently verified canonical artifact in the fixed C1
> capture-output root can become the selected C2 snapshot.

The next milestone may then consume the selected verified snapshot in the
reliable manual paper-cycle pipeline. C3 itself does not execute that pipeline.

## 38. Final C3 controlled production acceptance

The frozen validation contract above is satisfied. C3 is **FULLY COMPLETE /
ACCEPTED** at final head `82ba29ae2c2cc6bb3544077db0ee21868e6d5693`.

### 38.1 Accepted source and release context

- current C3 branch head before this documentation closeout:
  `82ba29ae2c2cc6bb3544077db0ee21868e6d5693`;
- accepted E3.7 source repair: `137bbe5a83d3bfe1cb62c381026c25e7fefa739a`;
- frozen production SQL: 118896 bytes, SHA-256
  `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`;
- accepted production wheel: `ai_trading_bot-0.1.0-py3-none-any.whl`,
  674358 bytes, SHA-256
  `b35bbe0adc8f55ea96cc9f9e1852015182d07ed32b98d86cc141129395e431d2`;
- broad source regression: 3186 passed, 17 skipped;
- Ruff, format, and `git diff --check` results were accepted;
- administrator deployment, Trading-account ACL republication, and non-admin
  production preflight were accepted.

### 38.2 Dedicated production identity and credential state

```text
identity: DESKTOP-I4DOKM7\Trading
SID: S-1-5-21-1397534616-3988210162-180023805-1009
administrator: False
```

The `/v2` credentials are immutable historical production inputs. They must not
be deleted, overwritten, restaged, or rotated in place. Future credential
rotation requires a separately reviewed `/v3` or later version.

### 38.3 Historical call #5

Call #5 remains permanently consumed historical evidence. Its request digest is
`c33949931607552c6f06503fadf818972fb4fe153dd2a65a21970e5e879a435e`. Its
durable terminal remains `FAILED / CONFIRMED` after the child/provider path
succeeded but parent publication failed. It is not successful and is not
retryable.

### 38.4 Final call #6 production acceptance

```text
ordered universe: SPY
request window: 2026-08-28 through 2026-08-28
target session date: 2026-08-29
authorized XNYS snapshot session: 2026-08-28
request digest: 67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
session_id: f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt_id: e809f393-b557-5c6b-8665-78d66822fee8
claim_id: 487618c1-a5a5-5dd9-971d-a1ea843194c5
reservation_id: fa5b4538-e475-5a13-9cb2-0d7936232c84
execution_id: d85a8085-137b-55c2-9679-cddade4a5907
terminal_id: b4c76e5f-44bb-54ce-a917-3e3223b84107
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
status: COMPLETED
terminal_state: SUCCEEDED
provider_call_disposition: CONFIRMED
exit code: 0
```

The one-shot CLI result was `COMPLETED` with terminal state `SUCCEEDED`,
provider-call disposition `CONFIRMED`, exit code 0, and durable selection and
snapshot IDs returned.

### 38.5 Final durable and offline proof

```text
DURABLE_ROW_FOUND=True
SESSION_STATE=SUCCESS_SELECTED
ATTEMPT_STATE=SUCCESS_SELECTED
CLAIM_STATE=COMMITTED
RESERVATION_STATE=TERMINAL_RECORDED
EXECUTION_PHASE=TERMINAL_RECORDED
TERMINAL_STATE=SUCCEEDED
PROVIDER_DISPOSITION=CONFIRMED
REQUEST_SHA256=67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
TERMINAL_SNAPSHOT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
SELECTION_SNAPSHOT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
DURABLE_MATCH=True
```

```text
ARTIFACT_EXISTS=True
ARTIFACT_BYTES=1291
ARTIFACT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
OFFLINE_VERIFY_STATUS=PASS
SNAPSHOT_ID=eba46838-44ae-5bec-97bf-98c6639ae6a7
SNAPSHOT_SESSION_DATE=2026-08-28
SNAPSHOT_SYMBOLS=['SPY']
ARTIFACT_EVIDENCE_MATCH=True
OFFLINE_SNAPSHOT_MATCH=True
C3_COMPLETION_EVIDENCE=True
```

Pre-effect evidence confirmed the exact production runtime, validated
production authority and frozen schema digest, immutable `/v2` credential
entries readable under the Trading SID, corrected E3.7 `CreateHardLinkW`
publication, absence of obsolete `FileLinkInfo`, a passing same-filesystem
publication canary, empty capture output, zero durable lineage, and no
provider/network operation during preflight.

### 38.6 Completion conclusion and next milestone

Architecture 82's stronger completion criterion is satisfied: one C1-approved
Trading process caused at most one C2-authorized provider attempt; secrets
remained in the contained child on the production effect path; C2 durable
process/resume fences governed the effect; the parent independently verified and
published the canonical artifact; the successful terminal was durably selected;
and independent post-run offline verification passed. C3 completion is not
merely Alpaca HTTP success.

Total actual C3 real-provider effects are **exactly 6**. All six are consumed;
call #6 is successful and consumed; no provider call #7 is authorized.

Production brokerage and live trading remain **NO-GO**. C3 does not authorize
brokerage credentials, broker reconciliation, order submission/cancel/replace,
real-money trading, unattended scheduling, automatic retry, automatic recovery,
or paper-account mutation.

The next product milestone is the reliable manually invoked paper cycle:

```text
verified C3 snapshot
-> strategy
-> proposals
-> deterministic risk
-> paper execution
-> durable before/after evidence
```

This closeout does not design that milestone in detail or create a new
architecture document.
