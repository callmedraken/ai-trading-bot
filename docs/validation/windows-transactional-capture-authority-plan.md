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

## 2. Enforcement acceptance split

The validation review must classify each assertion before accepting it.

The signed bootstrap and immutable `authority_metadata` own the permitted
descriptor and select authority/claim policy versions. This release supports
exactly `authority-policy/v1` and `claim-policy/v1`; the reviewed transaction
helper rejects any other signed value before request canonicalization, session
identity construction, or insertion, then reconciles metadata and request
semantics. SQLite preserves accepted canonical request bytes/digest and checks
copied descendant policy fields, but does not parse request JSON, validate
`Symbol` semantics, decide which future policies a release implements, or
authenticate external Alpaca behavior.

| SQLite fixture proves | Reviewed transaction harness proves |
| --- | --- |
| Immediate-parent foreign keys and `PRAGMA foreign_key_check` | Multi-statement workflow ordering |
| Normalized copied-policy checks from metadata through execution | Exact release-supported metadata policy validation before session creation |
| Append-only evidence, canonical resume-intent/receipt bytes, immutable rows, and prohibited deletes | Exact request snapshot, shape/type/date/Symbol validation, canonical request/digest, and policy reconciliation |
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
- session inserts match both signed metadata policies; attempts match their
  session claim policy and metadata provider/operation; claims match attempt
  policy; reservations match claim policy and owning-session authority policy;
  and executions match reservation authority policy/release;
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

Table-driven negative tests remove each required field in turn and cover an
unknown field; request-limit string, boolean, zero, and universe mismatch;
tuple, empty, oversized, duplicate, blank/whitespace/lowercase/padded/overlong/
unsupported-punctuation/normalization-equivalent, and non-string-member
universes; malformed/noncanonical dates and invalid ordering; wrong scalar
types; every fixed-value drift; metadata drift; and legacy labels. Every
rejection must leave no session, counter, attempt, claim, reservation,
execution, terminal, selection, recovery, or fake side-effect event. A
collision test proves that an alternate tuple representation which would feed
the same pure list framing cannot persist under the valid session ID. Mutation
tests change the original list, replace request fields, and alter target/date
facts after snapshot creation; the frozen snapshot, canonical bytes, digest,
identity, target date, and persisted row must remain mutually consistent. Tests
also prove that the snapshot has no mutable caller-owned fields, cannot be
assigned to, and serializes `ordered_universe` back to the established JSON
list representation. The positive complete lifecycle must persist the public
descriptor values in metadata, attempt, claim, canonical request bytes, and
all dependent identity material.
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
`commit_process_intent` -> fake `CreateProcessW` hook with the winner's opaque
permit -> `record_execution` with the exact typed successful process/Job
receipt -> `commit_resume_intent` and
`RESUME_INTENT_COMMITTED` -> fake `ResumeThread` hook with the winner's opaque
permit -> `record_post_resume_evidence` with the exact returned receipt ->
`record_terminal` -> selection when applicable. No persistence helper creates
a resume result.

The following duplicate operations must fail without a second side effect:

- a second claim for one attempt;
- a second reservation for one claim;
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

Session close-fact tests require `closed_at_utc` and `close_reason` to remain
jointly null before closure, become jointly non-null only on
`OPEN -> CLOSED` or `SUCCESS_SELECTED -> CLOSED`, and remain unchanged
forever. Partial population, pre-closure population, replacement, clearing,
and same-state `CLOSED` mutation all fail.

The trigger verifies open-session eligibility, target existence, same-session
lineage, current ordinal, and an exact action-matrix entry. The test transaction
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

### Final capability audit matrix

The executable audit distinguishes integrity from provenance: canonical bytes
and digests prove content, while a private typed issuer and a registry entry
binding the permit to the exact object prove test-adapter issuance. Copies,
reconstructions, wrong issuers, wrong permits, reuse, cross-lineage use, and
objects delayed past a persisted revocation all fail.

| Boundary | Required persisted parent | Capability/evidence | Issuer/provenance | Consumption point | Lifecycle arbiter | Database transaction | Revoking facts | Crash result / recovery | Direct-SQL gate tested |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Provider construction | `COMMITTED` claim, `OPEN` session | Claim identity and canonical request | Reviewed service; no adapter result | No opaque permit; once in normal workflow | No | No | Later reservation/recovery/terminal/selection/close facts | Claim remains consumed; no reconstructed provider action | Claim admission triggers; API occurrence is not SQL-provable |
| Process-intent issuance | `COMMITTED` reservation and normalized active lineage | `FakeProcessIntent` | Private issuer and exact object/permit registry | At dispatch | Persisted writers use SQLite serialization | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | No commit means no intent; committed intent is never reconstructed and uses unknown-process recovery | Intent append/state triggers |
| Process dispatch | `PROCESS_INTENT_COMMITTED`, committed claim, launch-reserved attempt, `OPEN`, no terminal/selection | Exact process intent | Private issuer and exact registered permit | Immediately before modeled `CreateProcessW` | Required through result production | No transaction across hook | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Missing persisted result is conservatively unknown | SQL cannot prove dispatch |
| Process-success persistence | Same active process lineage, no execution | `FakeProcessCreationReceipt` | Private adapter issuer and exact registered result permit | After successful commit | Required | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves retry while active; otherwise unknown-process recovery | Execution parent and reservation state triggers; provenance is service-only |
| Process-failure persistence | Same active process lineage, no execution/failure | `FakeProcessCreationFailure` with `NOT_CREATED` | Private adapter issuer and exact registered result permit | After successful commit | Required | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves retry while active; otherwise unknown-process recovery | Failure evidence/state triggers; provenance is service-only |
| Resume-intent issuance | `PRE_RESUME_READY`, `PROCESS_CREATED`, `OPEN`, no terminal/selection | `FakeResumeIntent` | Private issuer and exact object/permit registry | At resume dispatch | Required against classification | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Pre-commit uses pre-resume recovery; post-commit uses unknown-resume recovery | Normalized phase/evidence trigger |
| `ResumeThread` dispatch | `RESUME_INTENT_COMMITTED` and exact active lineage | Exact resume intent | Private issuer and exact registered permit | Immediately before modeled call | Required through receipt production | No transaction across hook | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Missing persisted receipt remains unknown | SQL cannot prove dispatch |
| Resume-success persistence | Same active resume lineage and current intent | `FakeResumeReceipt` | Private resume-result issuer and exact registered result permit | After successful commit | Required | `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Transient rollback preserves exact receipt while active; otherwise unknown-resume recovery | Normalized phase/evidence trigger; provenance is service-only |
| Terminal recording | Exact state/disposition/snapshot matrix | Canonical terminal evidence | Reviewed service and terminal policy | Unique terminal insert | No | `BEGIN IMMEDIATE` | Existing terminal, selection, `CLOSED`; manual review only permits conservative close | Rollback leaves no terminal | Terminal matrix and uniqueness triggers |
| Selection | Confirmed successful terminal and owning `OPEN` session | Terminal identity and selection request | Reviewed service and selection policy | Unique session selection | No | `BEGIN IMMEDIATE` | Existing selection, `SUCCESS_SELECTED`, `CLOSED` | Rollback leaves no selection | Selection ownership/state trigger |
| Recovery classification | `OPEN` session and exact action predecessor | Target, operator evidence, policy, current ordinal | Reviewed recovery service | Recovery row, ordinal, and state commit together | Required for reservation actions | `BEGIN IMMEDIATE` | Changed predecessor, prior classification, `SUCCESS_SELECTED`, `CLOSED` | Rollback consumes no ordinal; commit grants no replacement capability | Recovery action/target trigger plus paired service transaction |

The table-driven capability test retains process intents, process success and
failure results, resume intents, and resume success receipts across every
relevant `MANUAL_REVIEW`, `TERMINAL_RECORDED`, `SUCCESS_SELECTED`, and `CLOSED`
boundary. Each delayed dispatch or persistence attempt must fail without a new
event or database mutation. Separate provenance cases reject direct
construction, exact-byte reconstruction, copied objects, wrong issuers, wrong
permits, reuse, and cross-lineage use. Injected SQLite trigger failures prove
that an active, valid process or resume result remains registered after
rollback and succeeds exactly once after the transient failure is removed.

## 9. Transaction boundary gates

`FakeSideEffects` observes the database through an independent connection.
The test proves the following event order:

| Commit/effect boundary | Required evidence |
| --- | --- |
| Claim commit -> credential/provider construction | The observer sees `COMMITTED` before the fake provider hook runs |
| Reservation commit -> process creation | The observer sees `COMMITTED` before the fake process hook runs |
| `PRE_RESUME_READY` -> resume-intent commit | One `BEGIN IMMEDIATE` winner appends the exact intent triple, exposes `RESUME_INTENT_COMMITTED`, and alone receives the opaque permit |
| Resume-intent commit -> external `ResumeThread` | The fake adapter accepts only that permit and sees the committed canonical intent plus process, Job Object, and resume-authorization evidence |
| External `ResumeThread` -> post-resume/cleanup commit | The exact canonical `RESUMED` receipt bound to execution and intent digest is required before `RESUME_RECORDED` |
| Ambiguous terminal -> retry | A second claim cannot be inserted and the claim count remains one |
| Any prior session claim -> new claim | The trigger admits only the exact retry-safe process-creation-failure lineage |
| Unknown resume recovery -> closure | Recovery row, ordinal increment, `MANUAL_REVIEW`, `CLOSED`/`MAY_HAVE_OCCURRED` terminal, and authorized session close preserve the frozen execution |
| Recovery classification -> outstanding resume permit | Per-reservation arbitration makes exactly one side first; a recovery winner emits no hook event, while a hook winner may be conservatively classified before receipt persistence |
| Recovery classification -> delayed resume receipt | Exactly one of classification or receipt persistence commits first; classification rejects the delayed receipt, while a committed receipt makes the narrow recovery ineligible |

The fake hooks do not read secrets, construct a provider, create a Windows
process, call a network, or invoke a real Windows API. The fake resume adapter
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

Two-connection process-dispatch/recovery tests force both arbiter orderings.
Recovery-first commits `MANUAL_REVIEW`, leaves the earlier process permit
unusable, and emits no `CreateProcessW` event. Dispatch-first consumes exactly
one intent, emits exactly one call, and produces exactly one typed result;
recovery may then conservatively classify the still-unpersisted result. A
second matrix races both successful and definitive-failure result persistence
against recovery. Persistence-first commits one result and makes the narrow
recovery ineligible; recovery-first freezes the lineage and rejects delayed
persistence without consuming or overwriting its typed result.

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

Additional two-connection races pair recovery with each resume boundary. An
intent/recovery race has exactly one valid winner. Hook/recovery tests force
both orderings under one per-reservation lifecycle arbiter: recovery-first
leaves the permit unconsumed and emits no modeled call, while hook-first emits
exactly one call and permits only conservative unknown-outcome classification
before receipt persistence. Receipt/recovery tests likewise force both
orderings: recovery-first preserves `RESUME_INTENT_COMMITTED` with no receipt
or cleanup, while receipt-first reaches `RESUME_RECORDED` and makes the narrow
recovery fail. Every outcome preserves one audit trail, no alternate permit,
and no authority from a classified, terminal, selected, or closed lineage.
These tests validate the reviewed in-process arbitration contract; SQLite
alone cannot establish whether a real external call is already in flight.

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
outcomes for claim commit -> provider construction -> reservation commit ->
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
