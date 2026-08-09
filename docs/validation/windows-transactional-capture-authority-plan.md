# Windows transactional capture authority validation plan

This plan validates the normalized test-only authority described in
`docs/architecture/77-windows-transactional-capture-authority.md`. The
executable fixture is
`tests/fixtures/transactional_authority_schema.sql`; the focused harness is
`tests/runtime/test_windows_transactional_capture_authority.py`.

This milestone does not implement production capture, credentials, provider
transport, Windows provisioning, scheduling, brokerage access, or real-money
trading. All external effects are fake hooks or database observations.

## 1. Evidence rules

Every schema/transaction test must:

- use a temporary local SQLite database with `PRAGMA foreign_keys=ON`;
- execute the complete fixture before inserting authority facts;
- use `BEGIN IMMEDIATE` for write workflows;
- use fixed semantic timestamps and explicit canonical bytes in deterministic
  test data; timestamps are facts and never UUID5 inputs;
- compare exact canonical bytes and SHA-256 digests where evidence is stored;
- preserve the database after rollback/crash-style assertions for inspection;
- report sanitized SQLite version, integrity results, and failure class; and
- never use credentials, real provider calls, brokerage APIs, or real-money
  orders.

The fixture and tests must not discover a schema by scanning a directory or
accept a legacy JSON claim as authority. Paths are test transport inputs only;
they are not deterministic identity inputs.

Authority provider and operation values must be sourced from the public
`trading_bot.market_data.ALPACA_DAILY_SNAPSHOT_DESCRIPTOR`: exactly
`alpaca-market-data` and `historical-stock-bars-v2-raw-usd-no-asof`. The test
harness may repeat those literals only in assertions that verify the public
descriptor; executable authority inputs must read its attributes.

The trusted `Trading` account assumption is explicit. Tests cover accidental
duplicates, cooperating approved processes, foreign-key integrity, and
transaction ordering. They do not claim to authenticate executables or defend
against malicious direct SQL by code already controlling the trusted token.

### Inter-process arbiter acceptance gates

The focused harness must use `multiprocessing.get_context("spawn")`, not fork
inheritance or threads, for lifecycle-arbitration acceptance. Every child opens
its own SQLite connection and independently derives and opens its arbiter from
the reservation identity. No SQLite connection, lock handle, permit registry,
typed capability, or external result is passed between children.

The deterministic arbiter identity is the lowercase SHA-256 digest of canonical
sorted-key UTF-8 JSON containing exactly `authority_epoch_id`,
`machine_authority_id`, `launch_reservation_id`, and literal label
`lifecycle-arbiter/v1`. Tests require a bounded digest-only file name and prove
that raw identities are absent. Source assertions reject `threading.RLock` and
any process-local reservation-lock dictionary as lifecycle arbitration.

The portable adapter root is resolved once from the executable harness module
to the absolute ignored path
`<repository-root>/.pytest_cache/ai-trading-bot-lifecycle-arbiters-v1`.
Behavioral and compact source assertions require that this is the sole adapter
root rule and reject `tempfile.gettempdir()`, environment-derived roots,
current-directory roots, PID/thread components, random components, and
per-boundary caller overrides. The filesystem root is not part of the digest.
The previously classified 20 arbiter call sites retain their categories; any
new root-regression worker construction is classified separately.

Two independently spawned processes receive different `TEMP`, `TMP`, and
`TMPDIR` values before interpreter startup and again before arbiter
construction, then change to different current directories. For the same
machine, epoch, and reservation they must report the exact same absolute root,
lock path, and unchanged digest suffix. The first process holds the lock until
an explicit event releases it; the second must remain blocked, then acquire
only after release. A shared modeled-effect gate must record exactly one effect.
Different reservation identities must still select different lock paths. No
sleep, temporary-directory fallback, cwd fallback, or timeout takeover is
accepted as synchronization or authority.

For each pair below, tests force both acquisition orders rather than accepting
a scheduler-dependent race:

- provider construction versus `CLASSIFY_LAUNCH_RESERVATION`;
- `CreateProcessW` dispatch versus `CLASSIFY_PROCESS_OUTCOME_UNKNOWN`;
- `ResumeThread` dispatch versus `CLASSIFY_RESUME_OUTCOME_UNKNOWN`;
- process-result persistence versus process-outcome classification; and
- resume-result persistence versus resume-outcome classification.

Recovery-first must commit one `MANUAL_REVIEW` audit trail and reject the
delayed boundary. It emits no provider, process, or resume event when that
effect has not already happened. Dispatch-first emits exactly one external
event and may then be conservatively classified while its result is
unpersisted. Persistence-first commits exactly one durable result and makes the
narrow recovery ineligible; recovery-first rejects delayed persistence without
changing the frozen lineage. Every child exits cleanly, every final database
passes `PRAGMA foreign_key_check`, and no alternate permit or retry appears.

One spawned child must terminate abruptly while owning the test file-lock
adapter under one temporary-directory environment. A new spawned recovery
worker with different `TEMP`, `TMP`, and `TMPDIR` values must then acquire the
same repository-anchored arbiter, reconcile durable state, append exactly one
conservative recovery, and emit no retry. This proves process-death release,
not Windows named-mutex `WAIT_ABANDONED` signaling or ACL correctness.
Production acceptance separately requires the fixed
`Global\\AITradingBot-Lifecycle-v1-<digest>` named mutex,
administrator-reviewed security-descriptor and owner/DACL validation, and
conservative handling of `WAIT_ABANDONED` as owner-death evidence rather than
API-outcome evidence. `Local\\` lifecycle arbitration is rejected.

Milestone A production acceptance must run cooperating approved processes in
different Windows sessions against one reservation and prove that every Trading
worker, scheduler/helper, recovery process, and approved administrator tool
derives and opens the exact same `Global\\` mutex and cannot enter its critical
section concurrently. This demonstrates one machine-wide lifecycle authority,
not one authority per interactive session. The fixed prefix and digest suffix
are not caller selectable. Creation/opening must use the administrator-reviewed
security descriptor whose owner and DACL admit only the approved administrator
and Trading principals required by the architecture. An existing object with
an unexpected type, owner, DACL, name, or other security property must fail
startup closed, without trying `Local\\` or any alternate name. Acceptance must
also reject lease, heartbeat, timeout-takeover, lock-stealing, and session-local
fallback behavior.

The portable file-lock tests are semantic inter-process arbitration tests only.
They do not validate the Windows `Global\\` namespace, cross-Windows-session
object visibility, named-mutex type or name validation, privileges, owner, DACL,
or other ACL behavior. This PR does not implement those production concerns;
namespace validation, mutex creation/opening, privilege and ACL provisioning,
and real Windows acceptance remain Milestone A work.

Another spawned child reconstructs provider and process-public fields under
its own process-local issuers and registries. Both attempts must fail as not
issued and leave durable state unchanged. Permits and results are therefore
explicitly non-pickleable authority: they are never transferred, reconstructed,
or reissued after process death.

Lock-order assertions require: no active SQLite transaction before arbiter
acquisition; complete lineage recheck only while the arbiter is held;
`BEGIN IMMEDIATE` and commit while retained for durable boundaries; no active
SQLite transaction at provider construction, `CreateProcessW`, or
`ResumeThread`; and arbiter release only after commit or typed-result
production. A terminal write uses the same reservation arbiter. Session close
is permitted only after its terminal/manual-review prerequisites have already
revoked every external capability; it cannot bypass that terminal arbitration
or authorize another effect.

The API-entry lock-order matrix is explicit:

| Category | Boundaries | Required executable assertion |
| --- | --- | --- |
| A. Supplied SQLite connection | process-intent issuance; process success/failure persistence; resume-intent issuance; resume-result persistence; terminal recording; all four reservation-classification recoveries; direct threaded harness acquisitions that use a local connection | require an exact `sqlite3.Connection` and reject `in_transaction` before arbiter construction, query, capability consumption, evidence/state mutation, or event emission |
| B. Stored SQLite observer connection | executable `FakeSideEffects.construct_provider`, `create_process`, and `resume_thread` external boundaries | call `_require_no_active_transaction(self.observer)` before registry lineage resolution or arbiter construction; zero SQL, event, consumption, or effect on rejection |
| C. Worker-owned SQLite connection | independent spawned boundary and recovery workers | acquire the arbiter before opening the worker-owned SQLite connection and before `BEGIN IMMEDIATE`; the boundary worker closes its setup connection before racing |
| D. Pure arbiter exercise | deterministic identity, exclusion, and process-death tests | no SQLite connection or transaction is involved |
| E. External boundary with no SQLite connection at entry | production adapter shape only; no such executable fake boundary is currently present | do not invent a caller-owned connection parameter; enter the arbiter transaction-free, perform final lineage observation beneath it, and hold no SQLite transaction across the effect |

The caller-transaction rejection matrix starts `BEGIN IMMEDIATE` before each
caller-connection boundary and uses an arbiter-construction probe plus SQLite
trace callback. Every case must raise the deterministic active-transaction
error with zero arbiter attempts and zero SQL statements, preserve
`connection.in_transaction`, all rows, every event list, and every one-shot
capability, and permit the caller to roll back explicitly. The service never
commits, rolls back, nests, or replaces caller work; a `SAVEPOINT` is equally
outside the permitted hierarchy. After rollback, the original constructed
provider, process result, and resume result remain usable exactly once while
their durable lineage remains active.

The stored-observer matrix repeats `BEGIN IMMEDIATE` and `SAVEPOINT` for all
three `FakeSideEffects` public external methods. Each case proves immediate
active-transaction rejection, zero arbiter construction/acquisition, zero
observer SQL after entry, zero new external events, no durable mutation, an
unconsumed capability, and an observer transaction left active for the caller
to end. After explicit rollback, the exact original capability succeeds once;
a second use fails without a second effect.

Two spawned deadlock regressions place process A in `BEGIN IMMEDIATE` while
process B holds the same reservation arbiter and begins classification. The
supplied-connection case enters process-intent issuance; the stored-observer
case enters `FakeSideEffects.construct_provider` with a valid provider permit.
Process A must reject without attempting the arbiter, retain and then
explicitly roll back its transaction, and leave its capability unconsumed.
Process B must then commit recovery normally, and the stored-observer case must
emit no provider-construction event. Named spawn queues and events plus bounded
joins establish ordering; success must not depend on a SQLite busy timeout or
a sleep.

The final source audit enumerates every executable
`InterprocessLifecycleArbiter` construction and assigns it to exactly one of
categories A-E. It requires guards before every supplied or stored connection
acquisition, proves category-C connection opening occurs after acquisition,
and records that category E has no executable harness instance. In particular,
the audit classifies all three `FakeSideEffects` methods as category B rather
than external-only/no-SQLite boundaries.

## 2. Enforcement acceptance split

The validation review must classify each assertion before accepting it.

The signed bootstrap and immutable `authority_metadata` own the permitted
descriptor and select authority/claim policy versions. This release supports
exactly `authority-policy/v1` and `claim-policy/v1`; the reviewed transaction
helper rejects any other signed value before request canonicalization, session
identity construction, or insertion, then reconciles metadata and request
semantics. Independently, SQLite uses native JSON1 at
`sessions_before_insert` to admit only the exact canonical persisted
`capture_request/v2`, bind its target/provider/operation semantics to session
and metadata columns, preserve its bytes/digest, and check copied descendant
request and policy fields. The reviewed service still owns mutable-input
snapshotting, use of public `Symbol`, release-policy support decisions, and
UUID5 derivation; SQLite does not authenticate external Alpaca behavior.

| SQLite fixture proves | Reviewed transaction harness proves |
| --- | --- |
| Immediate-parent foreign keys and `PRAGMA foreign_key_check` | Multi-statement workflow ordering |
| Normalized copied-policy checks from metadata through execution | Exact release-supported metadata policy validation before session creation |
| Canonical session-request admission and redundant target/descriptor binding; append-only evidence, canonical resume-intent/receipt bytes, immutable rows, and prohibited deletes | Exact caller-input snapshot, public `Symbol` validation, canonical request construction, UUID5 derivation, and release-policy reconciliation |
| Unique one-to-one claim/reservation/execution/terminal/selection fences | UUID5 identity construction and comparison |
| Per-session uniqueness and trigger-owned ordinal increments | Commit-before-side-effect boundaries |
| Session-wide claim admission through normalized lineage joins | Complete atomicity of state plus evidence updates |
| Typed recovery target lineage, exact action matrix, policy, and operator digest | Pairing recovery insertion, counter allocation, and state update |
| Monotonic local state transitions and absorbing fences | External Windows evidence acquisition and classification |
| Fixed enums, budget, digest lengths, and typed success facts | UUID5 computation and exact material contract |

The review rejects any document or test claim that SQLite authenticates an
executable, verifies Windows CNG/ACL state, validates a provider response, or
protects against compromised trusted-token code. Cross-row triggers are
limited to database facts reachable through normalized immediate-parent joins
and do not inspect or prove excluded Windows effects.

### Persisted evidence-pair inventory and negative matrix

The schema audit must discover every column ending in `_json`, map it to its
declared SHA-256 digest, and compare the discovered set with this complete
inventory. A future persisted JSON column without an inventory entry or an
authoritative digest guard fails the test.

| Table | Persisted JSON/digest pairs | Ownership and authoritative boundary |
| --- | --- | --- |
| `authority_metadata` | metadata | owned; metadata insert trigger |
| `schema_migrations` | migration | owned; migration insert trigger |
| `sessions` | request | owned; session insert trigger |
| `attempts` | request; allocation evidence; attempt evidence | copied from session; owned; owned; attempt insert trigger |
| `provider_call_claims` | request; claim evidence | copied from attempt; owned; claim insert trigger |
| `launch_reservations` | reservation evidence; process intent; process-creation failure | owned at insert; appended on update; appended on update |
| `launch_executions` | process creation; Job Object; resume authorization; resume intent; post-resume; cleanup | first three owned at insert; last three appended on update |
| `terminals` | terminal evidence; sanitized diagnostics | owned; terminal insert trigger before the state/disposition matrix |
| `session_selections` | selection evidence | owned; selection insert trigger |
| `manual_recoveries` | operator evidence | owned; recovery insert trigger |

For each owned-at-insert pair, the table-driven boundary test supplies changed
bytes with the prior digest and a changed digest with the prior bytes, and
requires the whole direct-SQL insert to fail. For copied request pairs, it also
supplies internally hash-valid child bytes/digest that differ from the
immediate parent, then attempts parent drift; both fail without child, state,
or counter side effects. For append-on-update pairs, it supplies the wrong
digest during the only permitted null-to-value transition and requires the
entire row to remain unchanged.

Terminal cases exercise `SUCCEEDED`, `FAILED`, `AMBIGUOUS`, and `CLOSED` with
both terminal-evidence and diagnostics bytes/digest mismatches. A malformed
successful terminal must not exist and therefore cannot be selected. Selection
cases independently corrupt the selection-evidence bytes and digest and prove
that the session state, attempt state, and counters remain unchanged. Every
negative path is followed by the corresponding valid insert or lifecycle so
the test distinguishes a digest rejection from an accidentally impossible
fixture state.

The audit treats `migration_digest` as the SHA-256 of `migration_json`.
`bootstrap_digest`, `database_identity_digest`, and
`application_release_digest` instead bind their named signed/bootstrap,
database, and release material. Reservation/terminal request digests are
lineage copies without a local JSON blob; terminal snapshot digest validates
snapshot content and selection snapshot digest copies it. These intentionally
different semantics are asserted so the `_json` inventory neither omits a
content pair nor invents a false adjacent pair.

Acceptance distinguishes five independent properties: content integrity is
the SQLite `sha256(blob) IS digest` write guard; lineage is exact
immediate-parent equality; provenance is the reviewed private typed issuer and
one-shot permit model; exclusion is the OS-backed inter-process arbiter; and
external provider or Windows effects remain outside SQLite's proof boundary.

## 3. Schema execution gates

The first gate runs the complete DDL with foreign keys enabled and asserts:

1. all ten intended tables are present:
   `authority_metadata`, `schema_migrations`, `sessions`, `attempts`,
   `provider_call_claims`, `launch_reservations`, `launch_executions`,
   `terminals`, `session_selections`, and `manual_recoveries`;
2. every foreign key points to a primary key or unique parent key, with the
   immediate-parent chain:

   ```text
   authority_metadata -> sessions -> attempts -> provider_call_claims
       -> launch_reservations -> launch_executions
       -> launch_reservations -> terminals
   ```

   and direct boundary references from migrations, selections, and recoveries;
3. `PRAGMA foreign_key_check` returns no rows after the valid lifecycle;
4. `PRAGMA integrity_check` returns `ok`; and
5. no prohibited copied ancestor identity columns exist:

   | Table | Allowed parent identity | Forbidden copied identities |
   | --- | --- | --- |
   | `provider_call_claims` | `attempt_id` | epoch, session, ordinal, allocation, copied claim parent |
   | `launch_reservations` | `claim_id` | epoch, session, attempt, allocation |
   | `launch_executions` | `launch_reservation_id` | epoch, session, attempt, claim |
   | `terminals` | `launch_reservation_id` | epoch, session, attempt, claim, execution |
   | `session_selections` | session and terminal | copied claim/attempt/epoch ancestry |
   | `manual_recoveries` | session plus typed target | five nullable target ancestor columns |

The review must not reintroduce a separate allocation table, allocation
identity, large composite lineage foreign key, or redundant ancestor column.
The executable DDL smoke test must also confirm that:

- `provider_call_claims_before_insert` can traverse only the normalized
  immediate-parent chain and is the authoritative claim-admission gate;
- session inserts begin exactly `OPEN` with both counters zero, null close
  facts, and both signed metadata policies; attempts match their session claim
  policy and metadata provider/operation; claims match attempt policy;
  reservations match claim policy and owning-session authority policy; and
  executions match reservation authority policy/release;
- reservation inserts accept only `COMMITTED` with all failure/outcome fields
  null;
- the first reservation outcome timestamp and both session close facts are
  write-once; and
- `launch_executions` contains the three nullable resume-intent columns, the
  `RESUME_INTENT_COMMITTED` phase, and executable append/phase triggers that
  require exact canonical intent and receipt bytes; and
- `CLASSIFY_PRE_RESUME_READY`, `CLASSIFY_RESUME_OUTCOME_UNKNOWN`, and their
  distinct recovery phase/policy/digest checks are present without copied
  ancestor columns.

### Canonical timestamp-v1 and causal-edge gates

The executable DDL is the authoritative timestamp boundary. All 14 persisted
timestamp columns must contain the same native SQLite `CHECK` semantics:
exactly 20 ASCII characters in `YYYY-MM-DDTHH:MM:SSZ`, year `0001..9999`, a
valid proleptic-Gregorian date, uppercase `T`/`Z`, hour `00..23`, minute and
second `00..59`, and no fractions, offsets, spaces, leap seconds, or
`24:00:00`. Nullable columns must apply the same expression whenever non-null.
The structural DDL assertion inventories every timestamp column and the
behavioral matrix exercises the actual expression through direct SQL.

Direct SQL must reject, atomically, missing zero padding, a space separator,
lowercase `t` or `z`, missing `Z`, numeric offsets, one- and three-digit
fractions, hour 24, minute or second 60, non-leap `2026-02-29`, February 30,
month 00 or 13, day 00, year 0000, arbitrary text, and leading or trailing
whitespace. It must accept `0001-01-01T00:00:00Z`, a valid leap day, the normal
fixed lifecycle values, and `9999-12-31T23:59:59Z`. A failed native parse must
evaluate false at the `CHECK`; SQL `NULL` must not accidentally admit an
invalid non-null value.

For every causal edge below, table-driven direct-SQL tests require a value one
second earlier to fail, equality to succeed, and a later value to succeed.
Each rejection compares the complete database before and after, verifies the
immutable predecessor is unchanged, and proves a newer wrong-lineage row
cannot satisfy an exact-parent predicate:

| Child timestamp | Required predecessor and acceptance gate |
| --- | --- |
| migration/session creation | singleton metadata creation; migration ordering is required by the metadata-first provisioning model |
| attempt creation | exact owning session creation |
| claim commit | exact attempt creation |
| reservation commit | exact claim commit |
| process-intent commit | exact reservation commit |
| execution creation | exact process-intent commit |
| first process outcome | execution creation for `PROCESS_CREATED`; process-intent commit for definitive creation failure; matching classification recovery plus reservation/intent predecessor for first `MANUAL_REVIEW` |
| resume-intent commit | exact execution creation |
| terminal recording | process-failure outcome for `FAILED/NOT_STARTED`; resume intent for confirmed or ordinary ambiguity results; matching recovery as an additional predecessor for recovery-classified ambiguity or closure |
| selection | exact referenced confirmed-success terminal, including earlier/equal/later and wrong-session-terminal cases |
| recovery | action-specific predecessor for all nine closed-matrix actions |
| session close | exact `CLOSE_SESSION` recovery for `OPEN`, or exact session selection for `SUCCESS_SELECTED` |

The recovery chronology matrix covers
`RECORD_ATTEMPT_AMBIGUITY`, `RECORD_CLAIM_AMBIGUITY`,
`CLASSIFY_LAUNCH_RESERVATION`, `CLASSIFY_PROCESS_OUTCOME_UNKNOWN`,
`CLASSIFY_PRE_RESUME_READY`, `CLASSIFY_RESUME_OUTCOME_UNKNOWN`,
`SELECT_COMMITTED_SUCCESS`, `CLOSE_SESSION`, and `ACKNOWLEDGE_RESTORE`.
Each case is repeated with a target from another session to prove that time
alone cannot substitute for normalized lineage. The close matrix separately
proves equality and later closure for both authorized paths and atomic
rejection immediately before the matching recovery or selection.

Timestamp tests must also prove that normal and recovery-driven selection use
the same valid deterministic selection timestamp, that
`selection.selected_at_utc >= terminal.recorded_at_utc` for its exact referenced
terminal, and that `selection.selected_at_utc <= session.closed_at_utc` for any
subsequent closure. They must also prove reservation outcome timestamps remain
write-once after the first accepted value. Timestamp values remain audit-only
and absent from UUID5 material; canonical JSON and every existing identity
golden vector must remain byte-for-byte unchanged.

## 4. Deterministic identity gates

The test harness uses the fixed namespace
`7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012` and the exact UTF-8 length framing:

```text
LF(s) = ASCII(decimal UTF-8 byte length) + ":" + s
```

It verifies the root request tuple and the exact normalized tuples for:

```text
migration_id/v1
attempt_id/v2
claim_id/v2
launch_reservation_id/v2
launch_execution_id/v2
terminal_id/v2
selection_id/v2
recovery_id/v2
```

The fixed migration vector remains:

```text
authority_epoch_id       = 12345678-1234-5678-9abc-def012345678
schema_version           = 3
migration_policy_version = migration-policy/v1
framed UTF-8 preimage    = 15:migration_id/v136:12345678-1234-5678-9abc-def0123456781:319:migration-policy/v1
migration_id             = b1114fec-2247-506d-bfda-74008355b312
```

The normalized derived vectors are asserted as independent golden outputs:

| Identity | Expected value |
| --- | --- |
| `session_id` | `80e64e2b-689f-5c0f-9076-bd251b55a9ee` |
| `attempt_id` | `550d4a64-0306-5f15-a0ab-f65722c790a2` |
| `claim_id` | `8a3ba04b-6548-577f-9773-2b30744b929f` |
| `launch_reservation_id` | `51e87e09-cea2-5828-8598-14dd053be048` |
| `launch_execution_id` | `f5727d7d-dd0b-50d8-8bf3-6ff2e44414e7` |
| `terminal_id` | `bfee46cc-85a7-5fa7-88cd-0d5468dc51ef` |
| `selection_id` | `f10c3fc1-49b0-554a-8fa7-d36fa4d1bee8` |
| `recovery_id` | `9aaadbb2-62af-58db-af21-b5208551ec01` |

These vectors use `ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id` and
`.operation` as identity material. Repeating the same descriptor-bound inputs
must reproduce every lowercase UUID5 value. Provider or operation drift must
either change the pure identity material or be rejected by session creation
before persistence. The migration vector remains unchanged because its
material contains neither field.

The review perturbs clocks, UUID4 values, Python hash seeds, object identity,
working directories, path spellings, environment values, process IDs, and
serialized evidence bytes. None may change an identity unless a semantic tuple
field changes. Changing the immediate parent or required semantic policy must
change the derived identity. Administrator-provisioned machine/epoch/key IDs
are classified as signed facts, not runtime UUID5 values.

Every policy-bearing identity helper requires its policy inputs explicitly;
calling one without them fails rather than silently selecting module
constants. Golden tests change supplied authority/claim policies and require
different session, attempt, claim, reservation, or execution identity
material. The supported values are unchanged, so all documented vectors must
remain byte-for-byte unchanged.

## 5. Lifecycle and parent-fence gates

The valid path is one transaction helper at each boundary:

```text
metadata + migration
  -> session
  -> attempt ordinal 0
  -> permanent claim
  -> launch reservation
  -> committed process intent
  -> typed CreateProcessW result
  -> launch execution (success only)
  -> successful terminal
  -> owning session selection
```

The request propagation gate is exact and immediate-parent scoped. Before any
canonicalization, UUID5 computation, transaction, or insert, session creation
is the only operation that accepts the caller-owned `capture_request/v2`
object. The service requires an exact dictionary, copies its top level once,
captures the exact input list as a new tuple, validates only those captured
values, and returns one frozen, slots-backed `ValidatedCaptureRequest` with no
reference to the caller's dictionary or list. Its exact ten-field key set is
`bar_interval`, `child_operation_version`,
`ordered_universe`, `output_policy_version`,
`permitted_provider_operation`, `provider_id`, `request_limit`,
`request_window_end_date`, `request_window_start_date`, and
`target_session_date`. No session-creation operation may read the caller-owned
objects after the snapshot exists. Attempt allocation reads the accepted session
bytes/digest; claim creation reads
the attempt bytes/digest; reservation creation reads the claim digest; and
terminal creation reads the reservation digest. Each insert rejects any
request-byte or digest mismatch, and descendant helpers do not reconstruct the
request. Snapshot serialization, request digest, `session_id` material,
`target_session_date`, and the inserted row must all consume that same
snapshot. The valid-lifecycle test uses a non-default date, ordered universe,
and consistent limit, then compares the exact bytes/digest in every stored
request-bearing row.

The session row is the sole canonical request owner, and
`sessions_before_insert` is its independent direct-SQL admission gate. Native
JSON1 must require a valid JSON object with exactly the ten named fields and no
missing, unknown, or duplicate key; exact string/array/integer JSON types; the
fixed bar, child, output, public-provider, and public-operation values; an
integer limit and duplicate-free canonical Symbol array each bounded by the
repository's `MAX_DAILY_SNAPSHOT_SYMBOLS = 100`; exact canonical date-only
values ordered `window_start <= window_end < target_session`; and an exact
SHA-256 digest. The embedded target date must equal
`sessions.target_session_date`, while embedded provider and operation must
equal the referenced metadata and public descriptor. The trigger reconstructs
the established sorted-key compact serialization with JSON1 and compares it to
the stored UTF-8 JSON BLOB, so whitespace, key reordering, duplicate keys,
alternate numeric forms, and other semantic-but-noncanonical encodings fail.
It does not recompute `session_id`; UUID5 remains service-owned and unchanged.

Before that construction, the session helper must begin `BEGIN IMMEDIATE`,
read the singleton metadata row, first require exact release-supported
`authority-policy/v1` and `claim-policy/v1`, verify its provider and operation
against the public Alpaca descriptor, and require the proposed request's
corresponding fields to agree exactly. Unsupported, aliased, legacy, cased, or
unknown future policy values fail before canonical bytes, UUID5, or insertion.
The validator requires exact dict/list/string/integer
types; boolean is not an integer; a nonempty and bounded universe; a positive
limit equal to the universe length; canonical
`YYYY-MM-DD` values ordered `window_start <= window_end < target_session`; and
the exact fixed bar interval, child/output policy versions, provider, and
operation. It must not coerce tuples, integers, dates, casing, underscores,
legacy names, or alternate operation labels. Every universe member is an exact
string passed to the public `trading_bot.domain.Symbol`; the validator requires
the original text to equal `str(Symbol(entry))` and detects duplicates over
those canonical strings. It rejects blank, whitespace-only, lowercase,
padded, over-ten-character, unsupported-punctuation, and
normalization-equivalent entries without trimming or uppercasing. Canonical
period and hyphen symbols remain accepted.

One consolidated direct-SQL canonical-request matrix covers target-column
mismatch; missing, unknown, duplicate, malformed, reordered, whitespace-added,
wrong-root, and wrong-typed JSON; boolean, string, real, zero, over-bound, and
universe-mismatched limits; empty, oversized, non-string, duplicate,
lowercase, padded, blank, overlong, and unsupported-punctuation universes;
malformed/noncanonical dates and all invalid date orderings; every fixed-value,
request/metadata provider-operation, and digest mismatch. Every rejection must
leave the complete database byte-for-row equivalent to its predecessor,
including unchanged metadata, no session or counter, and no descendant. Each
case is followed by insertion of the corresponding valid canonical request so
the matrix distinguishes authoritative rejection from an accidentally
impossible fixture state.

The service-side table-driven matrix additionally removes each required field
in turn and covers tuple and normalization-equivalent input, legacy labels,
metadata drift, and caller mutation. A collision test proves that an alternate
tuple representation which would feed the same pure list framing cannot
persist under the valid session ID. Mutation tests change the original list,
replace request fields, and alter target/date facts after snapshot creation;
the frozen snapshot, canonical bytes, digest, identity, target date, and
persisted row must remain mutually consistent. Tests also prove that the
snapshot has no mutable caller-owned fields, cannot be assigned to, and
serializes `ordered_universe` back to the established JSON list representation.
The positive complete lifecycle must persist the public descriptor values in
metadata, attempt, claim, canonical request bytes, and all dependent identity
material.
Existing canonical JSON bytes and UUID5 golden vectors must remain unchanged.

Policy-lineage tests insert unsupported authority and claim metadata policies
separately and require no session, counter, descendant row, or fake side
effect. The valid lifecycle compares one exact lineage:
metadata authority/claim -> session authority/claim -> attempt claim -> claim
claim -> reservation authority/claim -> execution authority. The helpers must
read these values from persisted parents. A reset-resistance test changes the
module's release-supported constants only after session commit and requires
all descendants to retain the original signed parent values.

Direct-SQL negative tests supply a mismatched attempt policy, claim policy,
reservation authority policy, reservation claim policy, and execution
authority policy while every other binding remains valid. Each insert must
abort without consuming an ordinal or leaving a child row. These checks use
normalized joins and add no copied ancestor identity or composite foreign key.

The focused suite asserts:

- metadata and migration insert successfully and remain immutable;
- session counters start at zero;
- attempt zero consumes exactly one ordinal;
- one claim can reference an attempt and remains `COMMITTED` permanently;
- one reservation can reference a claim;
- one execution can reference a reservation;
- one terminal can reference a reservation, including a process-creation
  failure with no execution row; and
- one confirmed successful terminal can be selected only by its owning session.
- all supported policy versions remain exact across the complete lineage, and
  terminal/selection/recovery identities receive their own row policy
  explicitly rather than through hidden identity-helper defaults.

Claim admission is exercised through both the transaction helper and direct
claim insertion. The only accepted prior claim lineage is
`TERMINAL_RECORDED` reservation plus digest-valid process-intent and
process-creation-failure evidence plus `FAILED`/`NOT_STARTED` terminal plus no
execution. The same table-driven matrix rejects no reservation, `COMMITTED`,
`PROCESS_INTENT_COMMITTED`, incomplete
`PROCESS_CREATION_FAILED`, `PROCESS_CREATED` without execution,
`MANUAL_REVIEW`, `PRE_RESUME_READY`, `RESUME_INTENT_COMMITTED`, `RESUME_RECORDED`,
`POST_RESUME_AMBIGUOUS`, `SUCCEEDED`, `AMBIGUOUS`, `CLOSED`, `CONFIRMED`,
`MAY_HAVE_OCCURRED`, success awaiting selection, `SUCCESS_SELECTED`,
`CLOSED`, and incomplete or contradictory lineage. The helper must contain no
independent unresolved-execution query.

Reservation insertion tests reject every state other than `COMMITTED` and
reject a `COMMITTED` insert with prepopulated intent/failure evidence or an
outcome timestamp. A `BEGIN IMMEDIATE` process-intent transaction must verify
the normalized claim/request/policy/evidence lineage, append exact canonical
intent bytes/digest/timestamp, advance exactly to `PROCESS_INTENT_COMMITTED`,
commit before the hook, and return an opaque permit only to its winner. Direct
state transition without paired evidence, second acquisition, replacement,
clearing, partial updates, and standalone timestamp mutation all fail.
Separate transition tests prove the outcome timestamp remains null at intent
commit and is assigned exactly once by `PROCESS_CREATED`,
`PROCESS_CREATION_FAILED`, or first `MANUAL_REVIEW`; later terminal/recovery
transitions preserve it; replacement and clearing fail; and terminal recording
cannot supply a missing value.

Terminal insertion is accepted only for this matrix:

| Terminal state | Provider disposition | Snapshot | Evidence gate |
| --- | --- | --- | --- |
| `SUCCEEDED` | `CONFIRMED` | present | `RESUME_RECORDED` execution with exact canonical intent-bound `RESUMED` receipt and cleanup pair |
| `FAILED` | `NOT_STARTED` | absent | `PROCESS_CREATION_FAILED` reservation with exact intent-bound `NOT_CREATED` failure evidence |
| `FAILED` | `CONFIRMED` | absent | `RESUME_RECORDED` execution with post-resume and cleanup pairs |
| `AMBIGUOUS` | `MAY_HAVE_OCCURRED` | absent | `RESUME_RECORDED` or `POST_RESUME_AMBIGUOUS` execution with both pairs |
| `CLOSED` | `MAY_HAVE_OCCURRED` | absent | `MANUAL_REVIEW` reservation |

The table-driven negative cases reject ambiguity with `NOT_STARTED` or
`CONFIRMED`, success without a snapshot, and every non-success snapshot. A
terminal request digest must equal the immediate reservation parent. After a
valid insert, execution, reservation, and attempt are advanced to
`TERMINAL_RECORDED` in the same transaction.

For an execution-backed lifecycle, the executable order is explicitly
reservation commit -> fake provider construction with its reservation-issued
permit -> `commit_process_intent` with the resulting one-shot constructed
provider -> fake `CreateProcessW` hook with the winner's opaque process permit
-> `record_execution` with the exact typed successful process/Job
receipt -> `commit_resume_intent` and
`RESUME_INTENT_COMMITTED` -> fake `ResumeThread` hook with the winner's opaque
permit -> `record_post_resume_evidence` with the exact returned receipt ->
`record_terminal` -> selection when applicable. No persistence helper creates
a resume result.

The following duplicate operations must fail without a second side effect:

- a second claim for one attempt;
- a second reservation for one claim;
- a second provider construction or constructed-provider use for one reservation;
- a second process intent or process-hook use for one reservation;
- a second execution for one reservation;
- a second terminal for one reservation;
- a second selection for one session; and
- selecting one terminal for two sessions.

The suite also attempts updates and deletes against immutable evidence. The
trigger or foreign-key result must preserve the original row and must not
create a repair path.

The lifecycle must also prove that a successful terminal is not a shortcut:
execution evidence is recorded as paired post-resume and cleanup evidence,
the execution reaches `RESUME_RECORDED`, the terminal matrix is satisfied, and
the terminal, execution, reservation, and attempt terminal-recorded updates
commit together before selection.

## 6. Lineage gates

Selection uses one executable trigger to resolve:

```text
terminal -> launch_reservation -> claim -> attempt -> session
```

The test attempts to select another session's successful terminal and expects
an immediate failure.

Recovery uses one `target_kind`/`target_id` pair. For each supported target
kind (`SESSION`, `ATTEMPT`, `CLAIM`, `LAUNCH_RESERVATION`, `TERMINAL`), the
suite attempts to recover another session's target and expects failure. No
large mismatched composite tuple is constructed because the normalized schema
has no such tuple.

The review also verifies that a recovery cannot be inserted for
`SUCCESS_SELECTED` or `CLOSED`, cannot reopen a claim/reservation, cannot
delete evidence, and cannot authorize another provider call. The permitted
action matrix is closed:

| Action | Target | Predecessor -> result | Permitted effect |
| --- | --- | --- | --- |
| `RECORD_ATTEMPT_AMBIGUITY` | `ATTEMPT` | `LAUNCH_RESERVED` -> `AMBIGUITY_RECORDED` | evidence-only uncertainty record |
| `RECORD_CLAIM_AMBIGUITY` | `CLAIM` | `COMMITTED` -> `AMBIGUITY_RECORDED` | evidence-only uncertainty record |
| `CLASSIFY_LAUNCH_RESERVATION` | `LAUNCH_RESERVATION` | `COMMITTED` -> `MANUAL_REVIEW` | classify the existing reservation |
| `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` | `LAUNCH_RESERVATION` | `PROCESS_INTENT_COMMITTED` -> `MANUAL_REVIEW` | freeze and conservatively classify committed-process-intent uncertainty |
| `CLASSIFY_PRE_RESUME_READY` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | conservative path before any resume intent exists |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | freeze and conservatively classify committed-intent/no-receipt ambiguity |
| `SELECT_COMMITTED_SUCCESS` | `TERMINAL` | `SUCCEEDED` -> `SUCCESS_SELECTED` | normal owning-session selection |
| `CLOSE_SESSION` | `SESSION` | `OPEN` -> `CLOSED` | close only after terminal/no-ambiguity preconditions |
| `ACKNOWLEDGE_RESTORE` | `SESSION` | `OPEN` -> `RESTORE_ACKNOWLEDGED` | acknowledgement evidence only |

There is no generic recovery state ladder. Recovery cannot manufacture normal
workflow states or fabricate an attempt progression. A legitimate concurrent
recovery race may commit consecutive ordinals for distinct existing uncertain
targets; a duplicate target or fabricated target is rejected.

The process-outcome recovery test requires `PROCESS_INTENT_COMMITTED`, paired
digest-valid intent evidence, no execution, no definitive failure evidence,
and valid operator evidence. It proves the recovery row, exact counter
increment, `MANUAL_REVIEW` transition, and preserved intent commit atomically;
then proves no process permit, hook, claim, or retry can be authorized. The
reservation-only `COMMITTED` recovery remains distinct and valid before any
process intent exists.

### Canonical identity-input gates

Persisted schema/version values used by deterministic identities must equal the
version encoded in the canonical UUID5 tuple. This release therefore admits
exactly the following values at direct-SQL insertion time:

| Identity-bearing table | Persisted column | Supported value | Rejected smoke values |
| --- | --- | --- | --- |
| `sessions` | `session_schema` | exact integer `1` | `0`, `2`, `99` |
| `attempts` | `attempt_schema` | exact integer `1` | `0`, `2`, `99` |
| `provider_call_claims` | `claim_schema` | exact integer `1` | `0`, `2`, `99` |
| `launch_reservations` | `launch_reservation_schema` | exact integer `1` | `0`, `2`, `99` |
| `launch_executions` | `launch_schema` | exact integer `1` | `0`, `2`, `99` |
| `terminals` | `terminal_schema` | exact integer `1` | `0`, `2`, `99` |
| `session_selections` | `selection_schema` | exact integer `1` | `0`, `2`, `99` |
| `manual_recoveries` | `recovery_schema` | exact integer `1` | `0`, `2`, `99` |

The executable DDL matrix performs all 24 unsupported direct inserts and
requires each to fail atomically. `authority_metadata.bootstrap_schema` and
`schema_migrations.schema_version` have different bootstrap/migration
semantics and are intentionally not tightened by this identity-version gate.
Canonical JSON bytes and every existing UUID5 golden vector must remain
unchanged.

The remaining identity-relevant scalar audit requires `request_limit` to be an
exact positive built-in integer matching universe length, provider-call budget
to be exact integer `1`, and caller-supplied attempt/recovery ordinal overrides
to satisfy the gates below. Textual identity inputs continue to come from the
validated immutable request snapshot or exact persisted parent values. The
audit must not broaden normalization or coerce alternate scalar types.

## 7. Attempt ordinal and crash gates

The attempt primitive is tested under immediate SQLite row-trigger semantics:

- two independent connections racing on one open session commit ordinals 0
  and 1 without duplication;
- stale ordinal 0 after allocation and future ordinal 2 fail;
- direct, no-op, regression, skip, and second counter updates fail;
- inserting an attempt and rolling back restores both the original counter and
  absence of the row;
- committing preserves the attempt and exact increment;
- the application helper performs one insert and no independent counter
  update; and
- two separate sessions each begin at ordinal zero.

Any caller-supplied ordinal override must have exact Python type `int`, must be
non-negative, and must equal the current counter. `False`, `True`, integral
floats, strings, `int` subclasses, and negative integers fail before UUID5
construction, evidence construction, transaction entry, or insertion. Exact
built-in integer zero and the current positive ordinal remain accepted. Every
rejection preserves all rows and both session counters.

The counter proof depends only on immutable attempts and contiguous committed
per-session ordinals. It does not use an application-maintained trigger flag,
deferred trigger, clock, or alternate ordinal search.

## 8. Recovery ordinal and crash gates

Recovery is tested with the same single-insert pattern:

- two independent connections racing recoveries on one open session commit
  consecutive ordinals 0 and 1;
- stale, future, duplicate, no-op, and invalid target ordinals fail;
- direct recovery-counter updates fail;
- rollback preserves row, counter, and any matrix-authorized target-state
  atomicity;
- commit preserves the immutable recovery row, increment, and authorized
  target state together;
- recovery rows cannot be updated or deleted;
- each independent session begins recovery at ordinal zero; and
- recovery after a successful selection or closed session fails.

The same exact built-in non-negative-integer contract applies to a
caller-supplied recovery ordinal before lifecycle-arbiter acquisition, UUID5
construction, evidence construction, or transaction entry. Rejection creates
no recovery row, consumes no ordinal, and changes no target state.

Session close-fact tests require `closed_at_utc` and `close_reason` to remain
jointly null before closure, become jointly non-null only on
`OPEN -> CLOSED` or `SUCCESS_SELECTED -> CLOSED`, and remain unchanged
forever. Partial population, pre-closure population, replacement, clearing,
and same-state `CLOSED` mutation all fail.

The insert trigger verifies an open session with no existing selection, target
existence, same-session lineage, current ordinal, and the complete currently
actionable predicate for the exact action-matrix entry. An immutable historical
fact with the same nominal predecessor is insufficient. The test transaction
service additionally performs any matrix-authorized state update in the same
`BEGIN IMMEDIATE` transaction. It never manufactures `CLAIM_COMMITTED`,
`LAUNCH_RESERVED`, `TERMINAL_RECORDED`, or `SUCCESS_SELECTED` through a generic
recovery update.

The pre-intent recovery gate separately requires one `PRE_RESUME_READY`
execution with digest-valid process, Job Object, and resume-authorization
evidence and no intent, receipt, or cleanup. It preserves manual handling
without granting resume authority.

The unknown-resume recovery gate requires one reservation in the owning open
session, exactly one `RESUME_INTENT_COMMITTED` execution, digest-valid process,
Job Object, resume-authorization, and canonical intent evidence, and no
persisted post-resume receipt or cleanup. Invalid target lineage, predecessor,
policy, operator digest,
execution count/phase, or post-resume evidence fails before a state change.
The accepted transaction appends one immutable recovery, consumes exactly its
allocated ordinal, changes only the reservation to `MANUAL_REVIEW`, preserves
the first outcome timestamp and frozen execution/evidence, and grants no new
claim or provider call. It permits only a subsequent
`CLOSED`/`MAY_HAVE_OCCURRED` terminal and authorized session close. Recovery
after `SUCCESS_SELECTED` or `CLOSED` remains rejected.

Recovery classification is also tested as an irreversible authority barrier.
The active resume lineage is exactly an `OPEN` session, a `PROCESS_CREATED`
reservation, no terminal and no session selection, the expected execution
phase, and digest-valid phase evidence resolved through the normalized parent
chain. `commit_resume_intent`, the fake `ResumeThread` hook, and delayed receipt
persistence must each recheck that full predicate; possession of a previously
issued permit or structurally successful receipt is not sufficient. Tests
classify at `PRE_RESUME_READY` and `RESUME_INTENT_COMMITTED`, then prove no
intent, hook event, receipt persistence, terminal success, selection, new
claim, or provider call can arise from that classified lineage. They repeat
the delayed-permit and delayed-receipt rejection after conservative terminal
recording and session closure. A delayed successful process receipt is likewise
rejected after `CLASSIFY_PROCESS_OUTCOME_UNKNOWN`, with no execution row.

Direct SQL attempts both guarded resume phase advances after `MANUAL_REVIEW`.
The executable trigger must reject them because its normalized parent query
requires `PROCESS_CREATED`, `OPEN`, no terminal, and no selection. The DDL
smoke gate executes both exact transitions on a valid active lineage and then
proves the same statements fail after recovery without relying on copied
ancestor identifiers.

### Durable fact / aggregate projection acceptance matrix

The executable review treats every aggregate state as a projection of
normalized durable facts, never as evidence by itself. Child admission must
require the documented immediate-parent predecessor; after the child exists,
the parent projection guard must require that exact fact. Paired evidence on a
single row is appended in the same guarded update as its state/phase. A direct
state-column update alone must never manufacture operational progress.

| Table | State/phase and predecessor | Durable fact before projection | Required immediate-parent lineage | Direct-SQL admission/projection gate | Recovery, selection, and close acceptance |
| --- | --- | --- | --- | --- | --- |
| `sessions` | insert -> `OPEN`; `OPEN -> SUCCESS_SELECTED`; `OPEN|SUCCESS_SELECTED -> CLOSED` | canonical row with zero counters/no close facts; selection; close recovery or existing selection plus immutable close facts | metadata -> session; selection -> terminal -> reservation -> claim -> attempt -> session; the exact close transition rechecks every current attempt lineage | reject every noncanonical insert, selection-free success, recovery-free or stale-recovery open close, and any mutable close facts | `CLOSE_SESSION` may close an empty session, but any current attempt must be terminal with exact terminal/selection lineage and none may be ambiguous |
| `attempts` | insert -> `ALLOCATED`; then `CLAIM_COMMITTED`, `LAUNCH_RESERVED`, optional `LAUNCH_MAY_HAVE_OCCURRED`, `TERMINAL_RECORDED`, `SUCCESS_SELECTED`, optional `CLOSED` | attempt evidence; claim; reservation; attempt-ambiguity recovery; terminal; selection; terminal/selection plus closed session | each fact resolves to the exact attempt and owning session | reject every projection without its listed fact and reject child insert under the wrong predecessor | ambiguity grants no retry; selected and closed states are absorbing |
| `provider_call_claims` | attempt `ALLOCATED` -> immutable `COMMITTED` claim | claim row precedes attempt claim projection | claim -> exact attempt -> open session with complete prior-claim admission matrix | insert trigger enforces copied request/provider/operation/budget/policy and predecessor; row is immutable | claim-ambiguity recovery is evidence-only and leaves `COMMITTED` |
| `launch_reservations` | claim/attempt -> `COMMITTED`; then `PROCESS_INTENT_COMMITTED`, `PROCESS_CREATED` or `PROCESS_CREATION_FAILED`, `MANUAL_REVIEW`, `TERMINAL_RECORDED` | reservation; process intent; execution or exact failure evidence; matching recovery; terminal | reservation -> claim -> attempt -> open session; execution/terminal reference exact reservation | process intent requires the current launch-reserved parent projection; reject created-without-execution, failed-without-failure, manual-review without a fresh matching recovery predicate, and terminal-without-terminal | each manual-review predecessor requires its exact action row plus current phase/evidence and no newer terminal/selection fact; no alternate recovery path |
| `launch_executions` | reservation process intent -> `PRE_RESUME_READY`; then `RESUME_INTENT_COMMITTED`, `RESUME_RECORDED`, optional `POST_RESUME_AMBIGUOUS`, `TERMINAL_RECORDED`, optional `CLOSED` | execution; resume intent; post-resume plus cleanup; attempt-ambiguity recovery; terminal; terminal plus closed session | execution -> reservation -> claim -> attempt -> open session | reject insert under wrong reservation state and every phase projection missing its paired evidence, fresh active-lineage predicate, recovery, terminal, or close | ambiguity projection rechecks no terminal/selection; external call occurrence remains outside SQLite and conservatively recoverable |
| `terminals` | eligible reservation/execution predecessor -> immutable terminal | terminal row precedes execution/reservation/attempt terminal projections | terminal -> reservation -> claim -> attempt -> open session; state-specific execution/failure/manual-review evidence | reject impossible predecessor, wrong request lineage, and every invalid state/disposition/snapshot/evidence combination | ambiguous/manual-review terminals cannot authorize selection |
| `session_selections` | successful terminal and terminal-recorded attempt in `OPEN` session -> immutable selection | selection row precedes attempt/session success projections | selection -> successful terminal -> reservation -> claim -> exact attempt/session | reject wrong session, non-success, non-terminal-recorded attempt, duplicate selection, and success projection without selection | normal and `SELECT_COMMITTED_SUCCESS` recovery use the same insert path and timestamp |
| `manual_recoveries` | exact action-matrix predecessor in `OPEN` session | recovery row at current ordinal, then trigger-owned counter increment, then optional state projection | target kind/id resolves through immediate parents to the same session | reject wrong predecessor/target/action, duplicate ordinal, standalone counter update, and recovery-owned state without recovery | evidence-only actions do not themselves mutate aggregate state; any optional ambiguity projection must cite that row; classification and close are atomic and irreversible |

Recovery insertion actionability and later projection freshness are separate
gates. Every action must satisfy its complete current predicate when the
immutable row is inserted; every state-producing row is then necessary but not
sufficient for a later projection. The matrix is executable acceptance
criteria:

| Recovery action | Required current predicate at INSERT | Required later projection recheck |
| --- | --- | --- |
| `RECORD_ATTEMPT_AMBIGUITY` | exact active attempt/claim/reservation/execution lineage; committed claim; launch-reserved attempt; `PROCESS_CREATED` reservation; resumed, digest-valid execution; open session; no terminal/selection | the same current predicate before optional attempt/execution ambiguity projection |
| `RECORD_CLAIM_AMBIGUITY` | the same exact active lineage, evidence, open-session, and no-terminal/no-selection predicate | none; no state or capability projection exists |
| `CLASSIFY_LAUNCH_RESERVATION` | exact active lineage; `COMMITTED` reservation; no process intent, failure, execution, terminal, or selection | the same current predicate before `MANUAL_REVIEW` projection |
| `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` | exact active lineage and digest-valid process intent; no failure, execution, terminal, or selection | the same current predicate before `MANUAL_REVIEW` projection |
| `CLASSIFY_PRE_RESUME_READY` | exact active lineage with one digest-valid `PRE_RESUME_READY` execution and no resume intent, receipt, cleanup, terminal, or selection | the same current predicate before `MANUAL_REVIEW` projection |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | exact active lineage with one digest-valid intent-only execution and no receipt, cleanup, terminal, or selection | the same current predicate before `MANUAL_REVIEW` projection |
| `SELECT_COMMITTED_SUCCESS` | exact successful terminal ownership, terminal-recorded lineage, open session, and no existing selection | normal selection ownership, success, terminal-recorded lineage, open session, and uniqueness guards |
| `CLOSE_SESSION` | complete current normalized close predicate in an open session with no existing selection, including every current attempt | the same complete predicate at `OPEN -> CLOSED`, including every attempt added after insertion |
| `ACKNOWLEDGE_RESTORE` | exact owning open session with no existing selection | none; no state or capability projection exists |

Focused direct-SQL acceptance must exercise both directions and preserve a full
before/after database snapshot on every rejection:

- session insert rejects `SUCCESS_SELECTED`, `CLOSED`, unknown state, nonzero
  attempt or recovery counter, and either pre-populated close fact;
- attempt claim/reservation/ambiguity/terminal/selection/close projections
  reject the missing claim, reservation, recovery, terminal, selection, or
  closed-session fact respectively;
- reservation `PROCESS_CREATED`, `PROCESS_CREATION_FAILED`, `MANUAL_REVIEW`,
  and `TERMINAL_RECORDED` reject missing execution, failure evidence, recovery,
  and terminal respectively;
- execution ambiguity, terminal, and close projections reject missing
  recovery, terminal, and closed-session lineage;
- session success and close reject missing selection or close recovery;
- reservation, execution, terminal, selection, and recovery inserts reject an
  impossible parent predecessor; and
- after deliberately seeding a terminal-looking attempt while omitting its
  normalized child facts, `CLOSE_SESSION` rejects both fabricated
  `TERMINAL_RECORDED` and fabricated `SUCCESS_SELECTED`, leaving no recovery,
  ordinal consumption, close facts, or session-state change;
- after inserting a valid `CLOSE_SESSION` row but before projecting closure,
  adding a new allocated attempt makes the exact session transition fail;
- after inserting each mutable reservation-classification row, a newly inserted
  execution, resume intent, or resume receipt makes the stale projection fail;
- after inserting attempt-ambiguity recovery, a newly inserted terminal makes
  both the attempt and execution ambiguity projections fail; and
- inserting attempt- or claim-ambiguity recovery after a terminal exists fails
  at recovery-row admission and consumes no ordinal;
- a valid raw selection deliberately inserted without aggregate projection
  blocks `SELECT_COMMITTED_SUCCESS`, `CLOSE_SESSION`, and
  `ACKNOWLEDGE_RESTORE` recovery insertion and consumes no ordinal; and
- a canonical process-intent update against a reservation whose attempt has not
  reached `LAUNCH_RESERVED` fails even though the intent bytes and digest are
  otherwise exact.

The positive ordering remains claim insert -> attempt claim projection;
reservation insert -> attempt reservation projection; process-intent commit ->
typed external result -> execution insert -> reservation process-created
projection; terminal insert -> execution/reservation/attempt terminal
projections; selection insert -> attempt/session success projections; and
recovery insert -> counter increment -> recovery-owned projection. Executable
DDL, `foreign_key_check`, `integrity_check`, the valid lifecycle, and all UUID5
golden vectors must continue to pass unchanged.

### Final capability audit matrix

The executable audit distinguishes four independent concerns: durable SQLite
authority, process-local provenance, OS-backed inter-process arbitration, and
external effects/results. Canonical bytes and digests prove content, while a
private typed issuer and immutable registry issuance record bind the exact
object to its original reservation and, where applicable, execution identity
inside its issuing process. Registry-side identities select the arbiter,
database lineage, and event attribution; caller-visible fields are validated
but never trusted for those choices. Copies, reconstructions, reflective
mutation, cross-process transfer, wrong issuers, wrong permits, reuse,
cross-lineage use, and objects delayed past persisted revocation all fail.

The executable provenance audit covers `FakeProviderConstructionPermit`,
`FakeConstructedProvider`, `FakeProcessIntent`, both process-result types,
`FakeResumeIntent`, and `FakeResumeReceipt`. For each object it forcibly mutates
a visible lineage field with `object.__setattr__`, requires a registry-binding
failure before arbiter construction, and proves no event, database mutation, or
permit consumption. Restoring the field must leave the exact original object
usable at its documented boundary. Provider-permit tests additionally prove
ordinary assignment to the reservation, issuer, and permit fails; mutation from
reservation A to B performs no query or event for B; both durable reservations
remain unchanged; and B's genuine permit remains usable exactly once.

| Boundary | Required persisted parent | Capability/evidence | Issuer/provenance | Consumption point | Lifecycle arbiter | Database transaction | Revoking facts | Crash result / recovery | Direct-SQL gate tested |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Reservation/provider-permit issuance | `COMMITTED` claim in an `OPEN` session | Unique reservation insert produces frozen `FakeProviderConstructionPermit` | Immutable registry record owns exact object and original reservation ID | At provider construction | SQLite serializes reservation writers | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, process intent, terminal, selection, `CLOSED` | Lost post-commit permit uses `CLASSIFY_LAUNCH_RESERVATION` | Unique claim reservation and normalized insert trigger; SQL cannot issue the permit |
| Provider construction | `COMMITTED` reservation and exact active normalized lineage; no process intent/execution/terminal/selection | Exact reservation-issued permit produces `FakeConstructedProvider` | Registry-bound ID selects arbiter, SQL lineage, event, and result; visible fields are checked only | Reservation permit immediately before construction; provider result after process-intent commit | Required through constructed-provider production | No transaction across hook | `MANUAL_REVIEW`, process intent, terminal, selection, `CLOSED` | Failure/loss remains `COMMITTED`; no reconstruction or repeat, classify reservation | SQLite proves reservation ownership, not provider construction |
| Process-intent issuance | `COMMITTED` reservation and normalized active lineage | Exact `FakeConstructedProvider` produces `FakeProcessIntent` | Private issuers and exact object/permit registries | Provider capability after commit; process permit at dispatch | Required against reservation recovery | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves exact provider capability; committed process intent uses unknown-process recovery | Intent append/state triggers; provider provenance is service-only |
| Process dispatch | `PROCESS_INTENT_COMMITTED`, committed claim, launch-reserved attempt, `OPEN`, no terminal/selection | Exact process intent | Private issuer and exact registered permit | Immediately before modeled `CreateProcessW` | Required through result production | No transaction across hook | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Missing persisted result is conservatively unknown | SQL cannot prove dispatch |
| Process-success persistence | Same active process lineage, no execution | `FakeProcessCreationReceipt` | Private adapter issuer and exact registered result permit | After successful commit | Required | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves retry while active; otherwise unknown-process recovery | Execution parent and reservation state triggers; provenance is service-only |
| Process-failure persistence | Same active process lineage, no execution/failure | `FakeProcessCreationFailure` with `NOT_CREATED` | Private adapter issuer and exact registered result permit | After successful commit | Required | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves retry while active; otherwise unknown-process recovery | Failure evidence/state triggers; provenance is service-only |
| Resume-intent issuance | `PRE_RESUME_READY`, `PROCESS_CREATED`, `OPEN`, no terminal/selection | `FakeResumeIntent` | Private issuer and exact object/permit registry | At resume dispatch | Required against classification | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Pre-commit uses pre-resume recovery; post-commit uses unknown-resume recovery | Normalized phase/evidence trigger |
| `ResumeThread` dispatch | `RESUME_INTENT_COMMITTED` and exact active lineage | Exact resume intent | Private issuer and exact registered permit | Immediately before modeled call | Required through receipt production | No transaction across hook | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Missing persisted receipt remains unknown | SQL cannot prove dispatch |
| Resume-success persistence | Same active resume lineage and current intent | `FakeResumeReceipt` | Private resume-result issuer and exact registered result permit | After successful commit | Required | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves exact receipt while active; otherwise unknown-resume recovery | Normalized phase/evidence trigger; provenance is service-only |
| Terminal recording | Exact state/disposition/snapshot matrix | Canonical terminal evidence | Reviewed service and terminal policy | Unique terminal insert | Required for the reservation revocation boundary | `BEGIN IMMEDIATE` | Existing terminal, selection, `CLOSED`; manual review only permits conservative close | Rollback leaves no terminal | Terminal matrix and uniqueness triggers |
| Selection | Confirmed successful terminal and owning `OPEN` session | Terminal identity and selection request | Reviewed service and selection policy | Unique session selection | No | `BEGIN IMMEDIATE` | Existing selection, `SUCCESS_SELECTED`, `CLOSED` | Rollback leaves no selection | Selection ownership/state trigger |
| Recovery classification | `OPEN` session and exact action predecessor | Target, operator evidence, policy, current ordinal | Reviewed recovery service | Recovery row, ordinal, and state commit together | Required for reservation actions | `BEGIN IMMEDIATE` | Changed predecessor, prior classification, `SUCCESS_SELECTED`, `CLOSED` | Rollback consumes no ordinal; commit grants no replacement capability | Recovery action/target trigger plus paired service transaction |

The table-driven capability test retains provider-construction permits,
constructed-provider capabilities, process intents, process success and
failure results, resume intents, and resume success receipts across every
relevant `MANUAL_REVIEW`, `TERMINAL_RECORDED`, `SUCCESS_SELECTED`, and `CLOSED`
boundary. Each delayed dispatch or persistence attempt must fail without a new
event or database mutation. Separate provenance cases reject direct
construction, exact-byte reconstruction, copied objects, wrong issuers, wrong
permits, reuse, and cross-lineage use. Injected SQLite trigger failures prove
that an active, valid process or resume result remains registered after
rollback and succeeds exactly once after the transient failure is removed.

## 9. Transaction boundary gates

`FakeSideEffects` observes the database through a persistent independent
connection. Each public external hook rejects an active transaction on that
stored observer before registry lookup or arbiter construction, then performs
its final read-only lineage observation beneath the arbiter with no transaction
open across the modeled effect. The test proves the following event order:

| Commit/effect boundary | Required evidence |
| --- | --- |
| Claim commit -> reservation commit | Exactly one reservation transaction wins and alone receives the opaque provider-construction permit |
| Reservation commit -> credential/provider construction | The observer sees the exact active `COMMITTED` reservation before consuming its one-shot permit |
| Provider construction -> process-intent commit | The exact registered `FakeConstructedProvider` is consumed only after `PROCESS_INTENT_COMMITTED` commits |
| Process-intent commit -> process creation | The observer sees `PROCESS_INTENT_COMMITTED` before the fake process hook runs |
| `PRE_RESUME_READY` -> resume-intent commit | One `BEGIN IMMEDIATE` winner appends the exact intent triple, exposes `RESUME_INTENT_COMMITTED`, and alone receives the opaque permit |
| Resume-intent commit -> external `ResumeThread` | The fake adapter accepts only that permit and sees the committed canonical intent plus process, Job Object, and resume-authorization evidence |
| External `ResumeThread` -> post-resume/cleanup commit | The exact canonical `RESUMED` receipt bound to execution and intent digest is required before `RESUME_RECORDED` |
| Ambiguous terminal -> retry | A second claim cannot be inserted and the claim count remains one |
| Any prior session claim -> new claim | The trigger admits only the exact retry-safe process-creation-failure lineage |
| Unknown resume recovery -> closure | Recovery row, ordinal increment, `MANUAL_REVIEW`, `CLOSED`/`MAY_HAVE_OCCURRED` terminal, and authorized session close preserve the frozen execution |
| Recovery classification -> outstanding resume permit | Per-reservation arbitration makes exactly one side first; a recovery winner emits no hook event, while a hook winner may be conservatively classified before receipt persistence |
| Recovery classification -> delayed resume receipt | Exactly one of classification or receipt persistence commits first; classification rejects the delayed receipt, while a committed receipt makes the narrow recovery ineligible |

The fake hooks do not read secrets, construct a real provider, create a Windows
process, call a network, or invoke a real Windows API. The modeled provider
boundary consumes only the exact reservation-issued permit and returns one
registered constructed-provider capability. The fake resume adapter
records the modeled external event and returns a canonical receipt only after
modeled success; modeled failure returns no receipt. The transaction helper
persists the success receipt only after the hook returns. SQLite proves the
one-reservation and one-intent durable fences, exact persisted bytes, and phase
transition, not that an external Windows API call occurred.

Launch-execution evidence is append-only. The tests reject standalone intent
writes, direct phase jumps, partial triples/pairs, wrong digests, replacement,
clearing, reassignment, same-phase rewrites, and any rewrite after terminal
recording. The only permitted mutations are
`PRE_RESUME_READY -> RESUME_INTENT_COMMITTED` with the exact canonical intent
triple, followed by `RESUME_INTENT_COMMITTED -> RESUME_RECORDED` with the exact
canonical receipt and complete cleanup pair. Identity and all pre-resume
evidence remain immutable.

The whole-model audit is compact and table-driven. It covers every insert-only
initial state, every mutable write-once field, one authoritative session claim
matrix, conservative recovery/closure for each ambiguous window, and every
attempt, claim, reservation, execution, terminal, selection, and recovery
transition. No ambiguity, success, `SUCCESS_SELECTED`, or `CLOSED` state may
authorize a claim, launch, resume, provider call, or other side effect. Every
rejection must leave the original row, counters, lineage, and evidence
unchanged.

Two independent connections first race `commit_process_intent` for one
reservation: exactly one gets an opaque permit and reaches the process hook,
the loser fails before the hook, one canonical intent is stored, and exactly
one modeled `CreateProcessW` event occurs. Direct hook use without a permit,
second use, reconstructed/non-typed authority, and cross-reservation use fail.
A restart after intent commit reconstructs neither a permit nor process-call
authority.

Two independent reservation transactions race one claim: exactly one inserts
the unique reservation, receives a provider-construction permit, and can emit
one modeled provider event; the loser has no capability and emits nothing.
Provider tests reject the original claim ID, existing-reservation
reconstruction, direct construction, copied objects, wrong issuers or permits,
cross-reservation use, and reuse. The resulting `FakeConstructedProvider` is
also exact, registered, one-shot, and same-reservation bound. Process-intent
issuance without it fails. An injected transaction rollback preserves that
exact provider object for one retry while active; recovery revokes the retry.
Modeled construction failure or loss before process-intent commit leaves the
reservation `COMMITTED`, permits no second construction, and uses only
`CLASSIFY_LAUNCH_RESERVATION`.

Exact `FakeProcessCreationReceipt` and `FakeProcessCreationFailure` gates bind
the reservation and committed process-intent digest. Success requires canonical
schema-1 suspended-child, Job Object, and resume-authority evidence. Failure
requires canonical schema-1 `NOT_CREATED` evidence. Missing, malformed,
missing/extra-field, noncanonical, wrong-digest, unknown-outcome,
wrong-intent/reservation, copied, reconstructed, wrong-issuer, wrong-permit,
reused, and cross-reservation results fail before
execution or failure persistence. Only the successful receipt may create a
`PRE_RESUME_READY` execution; only the definitive failure may create the sole
retry-safe `FAILED`/`NOT_STARTED` lineage. Both persistence functions hold the
per-reservation arbiter, recheck the normalized active lineage, and consume the
registered result only after commit. Injected transient rollback preserves the
same exact result for one retry while the parent remains active.

A crash after process-intent commit before `CreateProcessW` and a crash after
the hook before result persistence expose the same
`PROCESS_INTENT_COMMITTED` row with no execution or definitive failure. Neither
case permits intent reacquisition, permit reconstruction, another process call,
or another claim. `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` preserves the intent,
records `MANUAL_REVIEW`, and allows only `CLOSED`/`MAY_HAVE_OCCURRED` plus the
authorized session-close path.

Spawned-process process-dispatch/recovery tests force both OS-arbiter
orderings using independent connections and independently opened arbiters.
Recovery-first commits `MANUAL_REVIEW`, leaves the process-local permit
unusable, and emits no `CreateProcessW` event. Dispatch-first consumes exactly
one intent, emits exactly one call, and produces exactly one typed result;
recovery may then conservatively classify the still-unpersisted result. A
second spawned matrix races result persistence against recovery.
Persistence-first commits one result and makes the narrow recovery ineligible;
recovery-first freezes the lineage and rejects delayed persistence without
overwriting durable evidence.

Two independent connections race `commit_resume_intent` for one execution:
exactly one gets a permit and reaches the hook, the loser fails before the
hook, one intent is stored, and one modeled `ResumeThread` event occurs. A
second intent, second use of the same permit, reconstructed/non-typed permit,
and cross-execution intent reuse all fail. A crash immediately after intent
commit before the hook and a crash immediately after the hook before receipt
persistence expose the same `RESUME_INTENT_COMMITTED` row with no receipt or
cleanup. Neither permits intent reacquisition, another hook attempt, a new
claim, or a `NOT_STARTED` classification. The separate pre-intent recovery
test proves `PRE_RESUME_READY` remains conservatively closable.

Additional spawned-process races pair recovery with each resume boundary. An
intent/recovery race has exactly one valid winner. Hook/recovery tests force
both orderings under one OS-backed inter-process lifecycle arbiter:
recovery-first
leaves the permit unconsumed and emits no modeled call, while hook-first emits
exactly one call and permits only conservative unknown-outcome classification
before receipt persistence. Receipt/recovery tests likewise force both
orderings: recovery-first preserves `RESUME_INTENT_COMMITTED` with no receipt
or cleanup, while receipt-first reaches `RESUME_RECORDED` and makes the narrow
recovery fail. Every outcome preserves one audit trail, no alternate permit,
and no authority from a classified, terminal, selected, or closed lineage.
These tests validate the test adapter's inter-process exclusion and crash
release semantics; SQLite alone cannot establish whether a real external call
is already in flight, and the adapter does not validate production mutex ACLs.

Receipt gates require exact `FakeResumeReceipt` type and the canonical object
`execution_id`, lowercase intent-digest hex, literal `RESUMED`, and exact
integer schema `1`. They reject `FAILED`, `ERROR`, `UNKNOWN`, wrong/string
schema, wrong execution or intent, missing/extra fields, noncanonical bytes,
wrong digest, direct construction, copied/reconstructed objects, wrong issuer,
wrong permit, reuse, and cross-execution use. Every rejection leaves
`RESUME_INTENT_COMMITTED` unchanged and prevents a successful terminal. The
positive path persists the same bytes/digest, consumes the adapter-issued
result permit only after commit, and proves `SUCCEEDED` is impossible until
exact receipt and cleanup evidence commit. A modeled failed hook issues no
receipt. An injected transient database failure leaves the valid receipt
registered and unconsumed for one exact retry while the lineage remains active.

The whole-boundary matrix covers positive, negative, concurrency, and crash
outcomes for claim commit -> reservation commit -> provider construction ->
process-intent commit -> `CreateProcessW` -> exact typed process result ->
`PRE_RESUME_READY` commit -> resume-intent commit -> `ResumeThread` -> exact
receipt/evidence commit -> terminal -> selection. One reservation plus one
process intent fences process creation; one resume intent fences resume; exact
typed results advance each boundary; every uncertainty blocks a claim; and
canonical request bytes and identity material retain the same validated
semantics. SQLite validates only persisted facts and fake-hook ordering; the
suite does not claim that SQLite proves a real `CreateProcessW`, `ResumeThread`,
Job Object, or other Windows API effect.

## 10. Security and operational gates not claimed by this fixture

The following remain administrator/manual or future production acceptance
work:

- fixed bootstrap canonicalization and detached signature verification through
  Windows CNG;
- owner/DACL, SID, reparse-point, final-handle, local-volume, and exact
  persistent-journal access checks;
- `PERSIST`/`synchronous=FULL` behavior under the dedicated Trading ACL,
  including no journal recreation, deletion, rename, or directory workaround;
- child-only Credential Manager reads, secret cleanup, process containment,
  Job Object verification, bounded streams, and native handle closure;
- real suspended-process evidence and conservative post-resume ambiguity;
- independently signed `backup_manifest/v1`, database/journal digest checks,
  historical-only restore, new generation/epoch, and empty executable DB;
- historical parsing of schema-1/2 artifacts without import or fallback; and
- unattended scheduling prerequisites and approval.

The validation must explicitly record that an internally consistent
same-generation database/journal replacement by Administrator/SYSTEM or
trusted-token code is outside this design's detection boundary.

## 11. Focused verification commands

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q tests/runtime/test_windows_transactional_capture_authority.py
.venv\Scripts\python.exe -m pytest -q tests/runtime/test_windows_transactional_capture_authority.py -k "canonical_authority_timestamp or every_authority_timestamp or creation_chain_timestamps or process_intent_timestamp or execution_timestamp or process_outcome_timestamp or resume_intent_timestamp or terminal_chronology or selection_timestamp or recovery_timestamp or session_close_timestamp"
.venv\Scripts\python.exe -m pytest -q tests/runtime/test_windows_transactional_capture_authority.py -k "arbiter_namespace or crash_releases_lifecycle_arbiter or lifecycle_arbiter_identity or arbiter_sqlite_boundaries or stored_observer_boundaries or lifecycle_transaction_guard or spawned_outer_transaction or spawned_stored_observer"
.venv\Scripts\python.exe -m pytest -q tests/runtime/test_windows_transactional_capture_authority.py -k "identity_bearing_rows or ordinal_overrides or recovery_insert_requires_action or recovery_action_matrix or recovery_projection"
.venv\Scripts\python.exe -m pytest -q tests/runtime/test_windows_transactional_capture_authority.py -k "complete_ddl or process_intent or process_hook or process_success_receipt or process_failure_result or crash_around_process or process_unknown_recovery"
.venv\Scripts\python.exe -m pytest -q tests/market_data/test_alpaca_daily_snapshot.py tests/cli/test_daily_snapshot_config.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

The focused suite is the executable acceptance gate for this schema revision.
The full suite and repository lint/format/diff checks are required before the
scoped commit. No command may access real credentials, real providers,
brokerage APIs, or real-money trading.
