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
descriptor. The reviewed transaction helper reconciles metadata and request
semantics before session identity construction or insertion. SQLite preserves
the accepted canonical request bytes/digest and descendant propagation, but is
not claimed to parse requests or authenticate external Alpaca behavior.

| SQLite fixture proves | Reviewed transaction harness proves |
| --- | --- |
| Immediate-parent foreign keys and `PRAGMA foreign_key_check` | Multi-statement workflow ordering |
| Append-only evidence, canonical resume-intent/receipt bytes, immutable rows, and prohibited deletes | Exact request shape/type/date validation, canonical request/digest, and policy reconciliation |
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

## 5. Lifecycle and parent-fence gates

The valid path is one transaction helper at each boundary:

```text
metadata + migration
  -> session
  -> attempt ordinal 0
  -> permanent claim
  -> launch reservation
  -> launch execution (optional)
  -> successful terminal
  -> owning session selection
```

The request propagation gate is exact and immediate-parent scoped. Before any
canonicalization, UUID5 computation, or insert, session creation is the only
operation that accepts and validates the exact `capture_request/v2` object.
Its exact key set is `bar_interval`, `child_operation_version`,
`ordered_universe`, `output_policy_version`,
`permitted_provider_operation`, `provider_id`, `request_limit`,
`request_window_end_date`, `request_window_start_date`, and
`target_session_date`. Attempt allocation reads the accepted session
bytes/digest; claim creation reads
the attempt bytes/digest; reservation creation reads the claim digest; and
terminal creation reads the reservation digest. Each insert rejects any
request-byte or digest mismatch, and descendant helpers do not reconstruct the
request. The valid-lifecycle test uses a non-default date, ordered universe,
and consistent limit, then compares the exact bytes/digest in every stored
request-bearing row.

Before that construction, the session helper must begin `BEGIN IMMEDIATE`,
read the singleton metadata row, verify its provider and operation against the
public Alpaca descriptor, and require the proposed request's corresponding
fields to agree exactly. The validator requires exact dict/list/string/integer
types; boolean is not an integer; a nonempty, bounded, duplicate-free universe
of nonempty strings; a positive limit equal to the universe length; canonical
`YYYY-MM-DD` values ordered `window_start <= window_end < target_session`; and
the exact fixed bar interval, child/output policy versions, provider, and
operation. It must not coerce tuples, integers, dates, casing, underscores,
legacy names, or alternate operation labels.

Table-driven negative tests remove each required field in turn and cover an
unknown field; request-limit string, boolean, zero, and universe mismatch;
tuple, empty, oversized, duplicate, blank-member, and non-string-member
universes; malformed/noncanonical dates and invalid ordering; wrong scalar
types; every fixed-value drift; metadata drift; and legacy labels. Every
rejection must leave no session, counter, attempt, claim, reservation,
execution, terminal, selection, recovery, or fake side-effect event. A
collision test proves that an alternate tuple representation which would feed
the same pure list framing cannot persist under the valid session ID. The positive
complete lifecycle must persist the public descriptor values in metadata,
attempt, claim, canonical request bytes, and all dependent identity material.

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

Claim admission is exercised through both the transaction helper and direct
claim insertion. The only accepted prior claim lineage is
`TERMINAL_RECORDED` reservation plus digest-valid process-creation-failure
evidence plus `FAILED`/`NOT_STARTED` terminal plus no execution. The same
table-driven matrix rejects no reservation, `COMMITTED`, incomplete
`PROCESS_CREATION_FAILED`, `PROCESS_CREATED` without execution,
`MANUAL_REVIEW`, `PRE_RESUME_READY`, `RESUME_INTENT_COMMITTED`, `RESUME_RECORDED`,
`POST_RESUME_AMBIGUOUS`, `SUCCEEDED`, `AMBIGUOUS`, `CLOSED`, `CONFIRMED`,
`MAY_HAVE_OCCURRED`, success awaiting selection, `SUCCESS_SELECTED`,
`CLOSED`, and incomplete or contradictory lineage. The helper must contain no
independent unresolved-execution query.

Reservation insertion tests reject every state other than `COMMITTED` and
reject a `COMMITTED` insert with prepopulated failure evidence or an outcome
timestamp. Separate transition tests prove the timestamp is assigned exactly
once by `PROCESS_CREATED`, `PROCESS_CREATION_FAILED`, or first
`MANUAL_REVIEW`; later terminal/recovery transitions preserve it; replacement
and clearing fail; and terminal recording cannot supply a missing value.

Terminal insertion is accepted only for this matrix:

| Terminal state | Provider disposition | Snapshot | Evidence gate |
| --- | --- | --- | --- |
| `SUCCEEDED` | `CONFIRMED` | present | `RESUME_RECORDED` execution with exact canonical intent-bound `RESUMED` receipt and cleanup pair |
| `FAILED` | `NOT_STARTED` | absent | `PROCESS_CREATION_FAILED` reservation with failure evidence |
| `FAILED` | `CONFIRMED` | absent | `RESUME_RECORDED` execution with post-resume and cleanup pairs |
| `AMBIGUOUS` | `MAY_HAVE_OCCURRED` | absent | `RESUME_RECORDED` or `POST_RESUME_AMBIGUOUS` execution with both pairs |
| `CLOSED` | `MAY_HAVE_OCCURRED` | absent | `MANUAL_REVIEW` reservation |

The table-driven negative cases reject ambiguity with `NOT_STARTED` or
`CONFIRMED`, success without a snapshot, and every non-success snapshot. A
terminal request digest must equal the immediate reservation parent. After a
valid insert, execution, reservation, and attempt are advanced to
`TERMINAL_RECORDED` in the same transaction.

For an execution-backed lifecycle, the executable order is explicitly
`record_execution` -> `commit_resume_intent` and
`RESUME_INTENT_COMMITTED` -> fake `ResumeThread` hook with the winner's opaque
permit -> `record_post_resume_evidence` with the exact returned receipt ->
`record_terminal` -> selection when applicable. No persistence helper creates
a resume result.

The following duplicate operations must fail without a second side effect:

- a second claim for one attempt;
- a second reservation for one claim;
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
| `CLASSIFY_PRE_RESUME_READY` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | conservative path before any resume intent exists |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | freeze and conservatively classify committed-intent/no-receipt ambiguity |
| `SELECT_COMMITTED_SUCCESS` | `TERMINAL` | `SUCCEEDED` -> `SUCCESS_SELECTED` | normal owning-session selection |
| `CLOSE_SESSION` | `SESSION` | `OPEN` -> `CLOSED` | close only after terminal/no-ambiguity preconditions |
| `ACKNOWLEDGE_RESTORE` | `SESSION` | `OPEN` -> `RESTORE_ACKNOWLEDGED` | acknowledgement evidence only |

There is no generic recovery state ladder. Recovery cannot manufacture normal
workflow states or fabricate an attempt progression. A legitimate concurrent
recovery race may commit consecutive ordinals for distinct existing uncertain
targets; a duplicate target or fabricated target is rejected.

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

Receipt gates require exact `FakeResumeReceipt` type and the canonical object
`execution_id`, lowercase intent-digest hex, literal `RESUMED`, and exact
integer schema `1`. They reject `FAILED`, `ERROR`, `UNKNOWN`, wrong/string
schema, wrong execution or intent, missing/extra fields, noncanonical bytes,
wrong digest, reuse, and cross-execution use. Every rejection leaves
`RESUME_INTENT_COMMITTED` unchanged and prevents a successful terminal. The
positive path persists the same bytes/digest and proves `SUCCEEDED` is
impossible until exact receipt and cleanup evidence commit.

The whole-boundary matrix covers positive, negative, concurrency, and crash
outcomes for claim commit -> provider construction -> reservation commit ->
`CreateProcessW` -> `PRE_RESUME_READY` commit -> resume-intent commit ->
`ResumeThread` -> exact receipt/evidence commit -> terminal -> selection. One
reservation fences process creation, one intent fences resume, exact receipt
proves modeled success, every uncertainty blocks a claim, and canonical
request bytes and identity material retain the same validated semantics.
SQLite validates only persisted facts and fake-hook ordering; the suite does
not claim that SQLite proves a real `CreateProcessW`, `ResumeThread`, Job
Object, or other Windows API effect.

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
