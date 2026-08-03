# Windows transactional capture authority

## Scope and decision

This milestone defines a normalized, executable SQLite authority for one
manually guarded, long-only market-data capture. It is a design and test
milestone, not production runtime, provisioning, credential, provider,
launcher, scheduling, or brokerage implementation. Paper operation remains
the default. Real-money trading is outside this boundary and is not enabled
by this design.

The authority is a deployment-pinned signed bootstrap plus one SQLite
database. A committed provider-call claim is permanent. The database, rather
than a directory scan, legacy file, launcher path, or output artifact, decides
whether the one permitted provider call may be attempted.

The fixed deployment is:

```text
F:\AITradingBot\Authority\
  authority.bootstrap.json
  authority.bootstrap.sig
  authority.sqlite3
  authority.sqlite3-journal
  capture-output\
  backup\
```

The bootstrap and its exact database/output paths are administrator-provisioned
facts. A caller, environment variable, child argument, current directory,
request, or database row cannot select an alternate authority root.

## 1. Security boundary retained by this revision

The approved security invariants are unchanged:

- The release reads only the fixed bootstrap and detached-signature paths.
- The bootstrap binds the machine authority, epoch, generation, approved SID,
  database path, output root, provider, operation, and policy versions.
- Bootstrap bytes are canonical and signed with the pinned P-256 key. Windows
  CNG verifies SHA-256 over the exact canonical bytes and accepts only the
  fixed 64-byte IEEE P1363 signature envelope.
- Every path component and final handle is checked for the exact local path,
  expected owner/DACL, and absence of reparse points, junctions, mounts,
  aliases, and UNC substitution.
- The administrator owns the bootstrap, signature, database replacement,
  persistent journal provisioning, and backup tree. Trading receives only the
  reviewed database/journal and capture-output rights.
- The trusted `Trading` token is an explicit assumption. SQLite constraints
  serialize accidental duplicate or cooperating approved processes; they do
  not authenticate an executable or protect against malicious direct SQL from
  code that already controls that token.
- Parent state is secret-free. Credential Manager access, provider transport,
  process creation, Job Object containment, native cleanup, and child
  isolation remain separate future runtime work.
- A provider response is hostile input and becomes evidence only after strict
  bounded validation and sanitization. Credentials, raw provider bodies,
  environment dumps, stdout, stderr, and arbitrary exception text are not
  authority evidence.

An older signed bootstrap, old epoch, altered signature, copied root, path
alias, mismatched database binding, or other independently detectable rollback
condition fails closed before mutation or side effect. A complete same-
generation replacement of the database and persistent journal is not
detectable from database-local state alone; that case is outside the stated
trust boundary. An approved restore is historical-only: rotate the signed
generation and epoch, provision a new empty executable database, and never
import old claims or attempts into the new executable epoch.

Unattended scheduling remains NO-GO until a separately approved milestone
covers launch-guard ACLs, trusted time and exchange-hours evidence, monitoring,
backup/restore, and scheduler/account rights.

## 2. Executable normalized relational model

The test-only source of truth is
`tests/fixtures/transactional_authority_schema.sql`. It executes with
`PRAGMA foreign_keys=ON` and contains all tables, indexes supplied by SQLite
for primary/unique keys, and triggers. There are no composite lineage foreign
keys. The authority chain is:

```text
authority_metadata
└── sessions
    └── attempts
        └── provider_call_claims
            └── launch_reservations
                ├── launch_executions
                └── terminals
```

The two boundary branches are `schema_migrations` directly below
`authority_metadata`, and `session_selections` plus `manual_recoveries`
directly below `sessions`.

### 2.1 authority_metadata

`authority_metadata` is a singleton active epoch row. It retains the signed
administrator facts: `authority_epoch_id` primary key,
`machine_authority_id`, bootstrap schema/generation, signing key, approved
SID, provider/operation, policy versions, provisioning timestamp, bootstrap
digest, database-local identity digest, canonical metadata bytes/digest, and a
singleton key constrained to `1`. It is immutable and cannot be deleted.

`authority_epoch_id` and `machine_authority_id` are not runtime UUID5
identities. They are administrator-provisioned facts bound by the signed
bootstrap.

The permitted provider contract is the existing public
`trading_bot.market_data.ALPACA_DAILY_SNAPSHOT_DESCRIPTOR`, whose exact
`provider_id` is `alpaca-market-data` and whose exact `operation` is
`historical-stock-bars-v2-raw-usd-no-asof`. The signed bootstrap and immutable
`authority_metadata` row own those two strings. The authority design does not
define aliases or a second authority-specific provider contract; this keeps it
compatible with `DailySnapshotCaptureConfig` and the strict Alpaca adapter.

### 2.2 schema_migrations

`schema_migrations` is an append-only direct child of metadata. It stores
`migration_id`, `authority_epoch_id`, schema/policy versions, migration and
release digests, canonical migration evidence, and the applied timestamp.
`UNIQUE(authority_epoch_id, schema_version)` permits one reviewed migration
fact for each schema in an epoch. It has no runtime migration or automatic DDL
path.

### 2.3 sessions

`sessions` is a direct child of metadata with:

- `session_id` primary key and `authority_epoch_id` foreign key;
- session/authority/claim policy versions and target session date;
- `state` in `OPEN`, `SUCCESS_SELECTED`, or `CLOSED`;
- `next_attempt_ordinal` and `next_recovery_ordinal`, both initially zero;
- canonical request bytes and digest; and
- creation plus controlled close facts.

Only forward session transitions are permitted. `SUCCESS_SELECTED` and
`CLOSED` are absorbing with respect to selection/recovery eligibility;
`CLOSED` also requires both `closed_at_utc` and `close_reason`. Those facts
must both be null before closure, may be populated exactly once while moving
either `OPEN` or `SUCCESS_SELECTED` to `CLOSED`, and cannot thereafter be
replaced, cleared, partially changed, or changed by a same-state `CLOSED`
update. Session identity and request evidence are immutable.

Session creation reconciles the proposed request before canonicalization or
identity derivation. In one `BEGIN IMMEDIATE` transaction, the reviewed
service reads the singleton `authority_metadata` row, verifies its provider and
operation exactly match `ALPACA_DAILY_SNAPSHOT_DESCRIPTOR`, and validates one
exact `capture_request/v2` object. Its key set is exactly
`bar_interval`, `child_operation_version`, `ordered_universe`,
`output_policy_version`, `permitted_provider_operation`, `provider_id`,
`request_limit`, `request_window_end_date`, `request_window_start_date`, and
`target_session_date`; no key is optional and no unknown key is accepted.

Every scalar string has exact string type. `ordered_universe` has exact list
type, is nonempty, contains at most the public
`MAX_DAILY_SNAPSHOT_SYMBOLS` bound, and contains only nonempty exact strings
with no duplicates. A tuple or other iterable is not equivalent.
`request_limit` has exact positive integer type (a boolean is not an integer
for this contract), equals the universe length, and does not exceed the same
bound. The three dates are exact canonical `YYYY-MM-DD`; the request window
start is no later than its end, and its end is strictly before the target
session date. `bar_interval=1d`, `child_operation_version=child/v1`,
`output_policy_version=output/v1`, and the provider/operation from the public
descriptor are fixed byte-for-byte. Metadata and request descriptor values
must also agree.

Only after every shape, type, bound, date, fixed-value, metadata, and
descriptor check succeeds may the service construct canonical JSON bytes,
derive `session_id`, and insert the session. Rejection leaves no session,
counter, attempt, claim, reservation, execution, terminal, selection, or
recovery side effect. Invalid alternate representations cannot enter storage
or exploit an identity collision with a valid request. Existing valid request
bytes and UUID5 vectors remain unchanged.

### 2.4 attempts

`attempts` replaces the former separate allocation entity. An attempt owns:

- `attempt_id` primary key and `session_id` immediate-parent foreign key;
- the unique per-session `ordinal`;
- provider and permitted operation;
- `provider_call_budget=1`;
- canonical request/digest bindings;
- attempt schema and policy versions;
- immutable allocation and attempt evidence bytes/digests;
- controlled local state; and
- creation timestamp.

`UNIQUE(session_id, ordinal)` is the ordinal fence. There is no
`allocation_id`, no separate allocation row, and no copied epoch or session
lineage on descendants. Attempt identity is checked by the reviewed
transaction helper before the insert; the trigger checks that the session is
open, the ordinal is exactly the current counter, the initial state is
`ALLOCATED`, and the budget is one.

The session is the sole canonical request owner. Only session creation accepts
or constructs the canonical request bytes and digest. Attempt allocation reads
those exact stored bytes and digest from its immediate parent; it does not
reconstruct the request or call a request-building helper. The attempt insert
trigger rejects any request-byte or digest mismatch.

### 2.5 provider_call_claims

Claims reference only `attempt_id`, which is `NOT NULL UNIQUE` and references
`attempts(attempt_id)`. The table stores the permanent `COMMITTED` state,
claim schema/policy, provider/operation/budget, request/digest bindings,
immutable claim evidence, and commit timestamp. It has no session, epoch,
ordinal, or allocation columns. Claim rows cannot be updated or deleted.

Claim creation reads the exact provider, operation, budget, request bytes, and
digest from its immediate attempt parent. The authoritative
`provider_call_claims BEFORE INSERT` trigger resolves the normalized
`claim -> attempt -> session` path and admits a claim only when the owning
attempt is `ALLOCATED`, its session is `OPEN`, the inserted claim is
`COMMITTED` with exact immediate-parent bindings, the session has no
selection or successful-but-unselected terminal, and every already-committed
claim in that session has the one retry-safe prior outcome.

That sole retry-safe outcome is an attempt in `TERMINAL_RECORDED` whose claim
has one reservation in `TERMINAL_RECORDED`, immutable SHA-256-valid
process-creation-failure evidence, a `FAILED`/`NOT_STARTED` terminal without a
snapshot, and no `launch_execution`. All other prior lineages block: no
reservation; `COMMITTED`; `PROCESS_CREATION_FAILED` without its terminal;
`PROCESS_CREATED` without an execution; `MANUAL_REVIEW`; any execution phase,
including `PRE_RESUME_READY`, `RESUME_INTENT_COMMITTED`, `RESUME_RECORDED`, or
`POST_RESUME_AMBIGUOUS`; any `SUCCEEDED`, `AMBIGUOUS`, or `CLOSED` terminal;
any `CONFIRMED` or `MAY_HAVE_OCCURRED` disposition; success awaiting
selection; an absorbing session; or incomplete/contradictory lineage. The
transaction helper performs no separate unresolved-execution query and relies
on this trigger for the same direct-SQL and helper boundary.

### 2.6 launch_reservations

Reservations reference only `claim_id`, which is `NOT NULL UNIQUE` and
references `provider_call_claims(claim_id)`. They store their own deterministic
identity, schema/release/policy bindings, request digest, immutable reservation
evidence, controlled reservation outcome, process-creation-failure evidence,
and timestamps. They have no session, attempt, allocation, or epoch columns.

`COMMITTED` is the pre-`CreateProcessW` fence. The controlled outcomes are
`PROCESS_CREATED`, `PROCESS_CREATION_FAILED`, `MANUAL_REVIEW`, and
`TERMINAL_RECORDED`. There is no reclamation, expiry, replacement, or second
reservation path.

Reservation creation reads the exact request digest from its immediate claim
parent. The reservation insert trigger verifies that digest binding and
requires every inserted reservation to start exactly in `COMMITTED`, with
process-creation-failure evidence and `outcome_recorded_at_utc` all null. A
known process-creation failure is therefore a later one-time
`COMMITTED -> PROCESS_CREATION_FAILED` update with matching evidence and a
non-null outcome timestamp; the failure pair cannot be replaced, cleared, or
partially written.

`outcome_recorded_at_utc` records the first post-reservation outcome. It moves
from null to a value exactly once on the first transition from `COMMITTED` to
`PROCESS_CREATED`, `PROCESS_CREATION_FAILED`, or `MANUAL_REVIEW`. Every later
transition, including `PROCESS_CREATED -> MANUAL_REVIEW` and
`TERMINAL_RECORDED`, preserves that exact value. Terminal recording cannot
supply a missing timestamp or overwrite, clear, or replace the first one.

### 2.7 launch_executions

Executions reference only `launch_reservation_id`, which is `NOT NULL UNIQUE`
and references `launch_reservations(launch_reservation_id)`. They store
process-creation, Job Object, resume-authorization, phase, post-resume, and
cleanup evidence, plus `resume_intent_json`, `resume_intent_digest`, and
`resume_intent_committed_at_utc`. The phase moves forward through
`PRE_RESUME_READY`, `RESUME_INTENT_COMMITTED`, `RESUME_RECORDED`,
`POST_RESUME_AMBIGUOUS`, `TERMINAL_RECORDED`, and `CLOSED`.

`commit_resume_intent(connection, execution_id) -> FakeResumeIntent` owns the
one-shot resume fence. In one `BEGIN IMMEDIATE` transaction it requires exactly
`PRE_RESUME_READY`, verifies the process-creation, Job Object, and
resume-authorization JSON/digest pairs, appends this exact canonical evidence,
and commits the phase change:

```json
{"execution_id":"<exact execution_id>","resume_operation":"ResumeThread","schema":1}
```

Only the transaction winner receives the opaque, typed in-memory permit.
Intent JSON, digest, and timestamp are one append-only triple: a second intent,
standalone field write, direct phase jump, clearing, replacement, reassignment,
or use for another execution fails closed. The permit is consumable once and
is not reconstructible from the database after restart. This durable intent is
the authority fence; it does not prove that Windows executed `ResumeThread`.

The fake external boundary accepts only that `FakeResumeIntent`, rechecks the
committed canonical intent and all pre-resume evidence, consumes the permit,
and returns a receipt only after the modeled call succeeds. A modeled failure
returns no successful receipt and leaves the database at
`RESUME_INTENT_COMMITTED`. The successful receipt body is exactly canonical
UTF-8 JSON:

```json
{"execution_id":"<exact execution_id>","resume_intent_digest":"<lowercase 64-character SHA-256 hex>","resume_result":"RESUMED","schema":1}
```

`record_post_resume_evidence` requires exact `FakeResumeReceipt` type, the
same execution and committed intent digest, exact field set and field types,
integer schema `1`, literal `RESUMED`, exact canonical bytes, and the exact
SHA-256 digest. `FAILED`, `ERROR`, `UNKNOWN`, missing/extra fields, wrong or
string schema, noncanonical bytes, wrong execution/intent/digest, receipt
reuse, and cross-execution reuse all fail. Only one
`RESUME_INTENT_COMMITTED -> RESUME_RECORDED` transaction may append that
receipt and the complete cleanup pair. Intent, post-resume, and cleanup
evidence cannot be replaced, cleared, partially written, or rewritten.
Identity, pre-resume evidence, and execution rows are immutable and cannot be
deleted. An execution is optional: a process-creation failure may still
receive a terminal directly from its reservation.

### 2.8 terminals

Terminals reference only `launch_reservation_id`, which is `NOT NULL UNIQUE`
and references `launch_reservations(launch_reservation_id)`. They contain
typed terminal state, provider-call disposition, request digest, immutable
evidence, optional verified snapshot digest, sanitized diagnostics, and the
recorded timestamp. They do not copy claim, attempt, session, epoch, or
execution identities. The reservation's one-to-zero-or-one execution
relationship tells the transaction service whether an execution exists.

`SUCCEEDED` requires `CONFIRMED` and a snapshot digest. `AMBIGUOUS` requires
`MAY_HAVE_OCCURRED`; failed process creation may be `FAILED` with
`NOT_STARTED`. The complete terminal state/disposition matrix is:

| Terminal state | Provider disposition | Snapshot | Required evidence |
| --- | --- | --- | --- |
| `SUCCEEDED` | `CONFIRMED` | present | execution is `RESUME_RECORDED` with the exact canonical success receipt bound to its committed intent and a cleanup pair |
| `FAILED` | `NOT_STARTED` | absent | reservation is `PROCESS_CREATION_FAILED` with paired failure evidence |
| `FAILED` | `CONFIRMED` | absent | execution is `RESUME_RECORDED` with both post-resume and cleanup pairs |
| `AMBIGUOUS` | `MAY_HAVE_OCCURRED` | absent | execution is `RESUME_RECORDED` or `POST_RESUME_AMBIGUOUS` with both pairs |
| `CLOSED` | `MAY_HAVE_OCCURRED` | absent | reservation is `MANUAL_REVIEW` with sanitized terminal evidence |

No other combination is permitted: in particular, ambiguity cannot claim
`NOT_STARTED` or `CONFIRMED`, success cannot omit its snapshot, and a
non-success terminal cannot carry a snapshot. The terminal insert trigger
verifies the exact request digest from its immediate reservation parent. After
the terminal row is inserted, the execution (when present), reservation, and
attempt are advanced to their terminal-recorded states in the same transaction.
For a manually classified unknown-resume execution, the execution instead
remains frozen at `RESUME_INTENT_COMMITTED`; the closure terminal advances only the
reservation and attempt and preserves the first reservation outcome timestamp.
Terminal rows are immutable and cannot be deleted.

### 2.9 session_selections

`session_selections` is intentionally narrow:

```text
selection_id       TEXT NOT NULL UNIQUE
session_id         TEXT PRIMARY KEY REFERENCES sessions(session_id)
terminal_id        TEXT NOT NULL UNIQUE REFERENCES terminals(terminal_id)
selection_schema   INTEGER NOT NULL
selection_policy_version
snapshot_digest
selection_evidence_json / selection_evidence_digest
selected_at_utc
```

One immediate foreign key points to the owning session and one to the selected
terminal. A `BEFORE INSERT` trigger verifies the terminal path
`terminal -> launch_reservation -> claim -> attempt` resolves to the same
`session_id`, that the terminal is a confirmed success, and that the selected
snapshot digest matches. The application transaction then commits the
selection and the session/attempt success transitions together.

### 2.10 manual_recoveries

Recoveries are direct session children with `recovery_id`,
`recovery_ordinal`, `target_kind`, and `target_id`. `target_kind` is exactly
one of `SESSION`, `ATTEMPT`, `CLAIM`, `LAUNCH_RESERVATION`, and `TERMINAL`.
There are no five nullable target columns and no copied ancestor identities.
The row also stores action, predecessor/resulting state, recovery policy/schema,
operator evidence, and creation timestamp. `UNIQUE(session_id,
recovery_ordinal)` fences each per-session ordinal.

The `BEFORE INSERT` trigger requires an open session, the current recovery
counter, a target that resolves through the immediate-parent chain to that
same session, and one exact closed action-matrix entry:

| Action | Target | Predecessor -> result | Effect |
| --- | --- | --- | --- |
| `RECORD_ATTEMPT_AMBIGUITY` | `ATTEMPT` | `LAUNCH_RESERVED` -> `AMBIGUITY_RECORDED` | record resume uncertainty; no fabricated attempt state |
| `RECORD_CLAIM_AMBIGUITY` | `CLAIM` | `COMMITTED` -> `AMBIGUITY_RECORDED` | record uncertainty; claim remains permanent |
| `CLASSIFY_LAUNCH_RESERVATION` | `LAUNCH_RESERVATION` | `COMMITTED` -> `MANUAL_REVIEW` | classify the existing reservation |
| `CLASSIFY_PRE_RESUME_READY` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | conservatively abandon a process that never received a resume intent |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | conservatively classify the committed-intent/no-receipt ambiguity |
| `SELECT_COMMITTED_SUCCESS` | `TERMINAL` | `SUCCEEDED` -> `SUCCESS_SELECTED` | invoke normal owning-session selection |
| `CLOSE_SESSION` | `SESSION` | `OPEN` -> `CLOSED` | close only when all attempts are terminal and none is ambiguous |
| `ACKNOWLEDGE_RESTORE` | `SESSION` | `OPEN` -> `RESTORE_ACKNOWLEDGED` | record restore acknowledgement only |

No generic recovery state ladder exists. Recovery cannot manufacture
`CLAIM_COMMITTED`, `LAUNCH_RESERVED`, `TERMINAL_RECORDED`, or
`SUCCESS_SELECTED` by arbitrary state update, cannot reopen or delete evidence,
and cannot authorize another provider call. A legitimate race may record
uncertainty for distinct existing targets, but it cannot fabricate an attempt
or advance one target twice. The `AFTER INSERT` trigger owns the exact counter
increment, and the reviewed transaction service performs any matrix-authorized
state update in the same `BEGIN IMMEDIATE` transaction.

`CLASSIFY_PRE_RESUME_READY` preserves the conservative operator path before
intent allocation. It requires one digest-valid `PRE_RESUME_READY` execution
with no intent, post-resume, or cleanup evidence, records `MANUAL_REVIEW`, and
grants no resume or other external authority.

`CLASSIFY_RESUME_OUTCOME_UNKNOWN` is deliberately narrow. The reservation
must belong to the open session, be `PROCESS_CREATED`, and own exactly one
`RESUME_INTENT_COMMITTED` execution with digest-valid process-creation, Job
Object, resume-authorization, and canonical resume-intent evidence. No
post-resume receipt/evidence or cleanup may have been persisted. This is the
persistently indistinguishable state for both a crash after intent commit but
before `ResumeThread` and a crash after `ResumeThread` but before receipt
persistence. The transaction verifies the target identity,
operator evidence digest, recovery schema/policy, predecessor, and requested
action; appends the immutable recovery row; advances the trigger-owned
recovery counter; and moves only the reservation to `MANUAL_REVIEW`. The
execution and its evidence remain unchanged. This action never infers
`NOT_STARTED` and grants no launch, claim, resume, or provider-call authority.
The only subsequent terminal classification is the existing
`CLOSED`/`MAY_HAVE_OCCURRED` entry, after which the normal authorized session
close may run. Recovery remains prohibited after `SUCCESS_SELECTED` or
`CLOSED`.

## 3. Enforcement split

The fixture deliberately enforces only facts that SQLite can evaluate at the
row boundary. The reviewed transaction service and transaction tests enforce
the multi-statement semantic contract.

The signed bootstrap and immutable metadata own the permitted public Alpaca
descriptor. The reviewed service performs descriptor and canonical-request
semantic reconciliation before session insertion. SQLite then preserves the
immutable canonical bytes/digest and exact descendant propagation; it does not
parse requests to authenticate or validate external provider behavior.

| SQLite schema, constraints, and triggers | Reviewed transaction service/tests |
| --- | --- |
| Immediate-parent foreign keys and `foreign_key_check` integrity | Workflow ordering across multiple statements and tables |
| Append-only immutable evidence, canonical resume-intent/receipt bytes, and prohibited deletes | Exact capture-request shape/type/date validation, canonical construction, digest reconciliation, and policy reconciliation |
| One-to-one claim, reservation, execution, terminal, selection, and ordinal fences | Multi-statement parent-state update sequencing |
| Unique per-session ordinals and trigger-owned exact increments | Commit-before-side-effect boundaries |
| Session-wide claim admission and normalized retry-safe lineage joins | Complete transaction atomicity and crash classification |
| Typed recovery target lineage, action matrix, policy, and operator digest | State updates paired with recovery insertion and counter allocation |
| Valid local monotonic state transitions and absorbing-state fences | External Windows evidence acquisition and classification |
| Digest lengths, fixed enum values, provider budget, and typed success facts | UUID5 identity computation and comparison against the reviewed contract |

SQLite does not authenticate executables, inspect Windows ACLs, verify CNG
signatures, read Credential Manager, validate provider responses, or protect
against malicious direct SQL from compromised trusted-token code. The
cross-row triggers enforce only database facts reachable through the
normalized immediate-parent joins; they do not inspect or prove Windows API
effects.

## 4. Ordinal primitives

### 4.1 Attempt allocation

The application transaction is:

```text
BEGIN IMMEDIATE
read sessions.next_attempt_ordinal
construct attempt_id from session_id and the read ordinal
INSERT exactly one attempts row
-- no independent counter UPDATE
COMMIT
```

The immediate `BEFORE INSERT` trigger verifies the session is `OPEN`, the
inserted ordinal equals the counter, the row starts in `ALLOCATED`, and the
provider budget is one. The immediate `AFTER INSERT` trigger performs the sole
`next_attempt_ordinal = next_attempt_ordinal + 1` update. The counter guard
accepts only `OLD + 1`, only when an immutable attempt row exists at the old
counter, and only when the new counter equals the committed attempt count.

Consequently a standalone update, no-op, regression, skipped ordinal, second
increment, attempt identity mutation, or deletion aborts. SQLite row triggers
run inside the inserting statement, so an abort rolls back both the attempt
row and the trigger-owned increment. Separate sessions independently begin at
ordinal zero.

### 4.2 Recovery allocation

Recovery uses the same single-insert primitive:

```text
BEGIN IMMEDIATE
verify epoch, session, target identity/digests, predecessor, operator evidence,
  recovery policy, and requested action
read sessions.next_recovery_ordinal
construct recovery_id from that exact ordinal
INSERT exactly one manual_recoveries row
AFTER INSERT advances next_recovery_ordinal by exactly one
apply the exact matrix-authorized state transition
COMMIT
```

The `BEFORE INSERT` trigger validates open-session eligibility, the current
ordinal, supported target kind, same-session target lineage, operator digest,
recovery schema/policy, predecessor, and exact action-matrix entry. The
`AFTER INSERT` trigger performs the sole exact counter increment. Its guard
uses the immutable recovery row at the old counter and the committed
per-session row count to reject direct updates, no-ops, regressions, skips,
second increments, and unpaired writes. Recovery rows cannot be updated or
deleted.

The row, trigger-owned increment, and authorized state transition share the
same transaction. A crash before commit leaves no recovery row and consumes
no ordinal; a crash after commit leaves the row, exact increment, and state
transition all durable. A duplicate ordinal fails closed and never silently
selects an alternate ordinal. Separate sessions independently begin at
recovery ordinal zero.

## 5. Deterministic identities

The repository-owned namespace is:

```text
7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012
```

For a Unicode string `s`, the exact length frame is:

```text
LF(s) = ASCII(decimal UTF-8 byte length) + ":" + s
```

The UUID5 name is the UTF-8 concatenation of `LF(material_label)` followed by
one length frame per tuple field. Integers are canonical base-10 ASCII;
UUIDs are lowercase canonical text; dates are `YYYY-MM-DD`; and an optional
value is an explicit empty frame. An ordered list is one framed field whose
contents are `LF(item_count)` followed by each item frame in caller-defined
order. No identity uses a clock, UUID4, Python hash, object identity, locale,
filesystem path, secret, row order, or serialized artifact bytes.

The root `session_id/v2` tuple is:

```text
machine_authority_id,
authority_epoch_id,
session_schema,
authority_policy_version,
claim_policy_version,
capture_request/v2,
target_session_date,
provider_id,
permitted_provider_operation,
UL(ordered_universe),
bar_interval,
request_window_start_date,
request_window_end_date,
request_limit,
child_operation_version,
output_policy_version
```

For the documented vectors, `provider_id` and
`permitted_provider_operation` are sourced directly from the public Alpaca
descriptor as `alpaca-market-data` and
`historical-stock-bars-v2-raw-usd-no-asof`. They are not independent literals
owned by this authority design.

Every derived identity uses its immediate parent plus the minimum semantic
facts needed to distinguish that row:

| Identity/material label | Exact tuple after the label |
| --- | --- |
| `migration_id/v1` | `authority_epoch_id, schema_version, migration_policy_version` |
| `attempt_id/v2` | `session_id, ordinal, provider_id, permitted_provider_operation, attempt_schema, attempt_policy_version` |
| `claim_id/v2` | `attempt_id, claim_schema, claim_policy_version, provider_id, permitted_provider_operation, provider_call_budget` |
| `launch_reservation_id/v2` | `claim_id, launch_reservation_schema, application_release_version, authority_policy_version, claim_policy_version` |
| `launch_execution_id/v2` | `launch_reservation_id, launch_schema, application_release_version, authority_policy_version` |
| `terminal_id/v2` | `launch_reservation_id, terminal_schema, terminal_policy_version` |
| `selection_id/v2` | `session_id, terminal_id, selection_schema, selection_policy_version` |
| `recovery_id/v2` | `session_id, target_kind, target_id, action, predecessor_state, resulting_state, recovery_schema, recovery_policy_version, recovery_ordinal` |

The test harness hard-codes these affected golden vectors for the fixed
semantic example:

| Identity | Expected lowercase UUID5 |
| --- | --- |
| `session_id` | `80e64e2b-689f-5c0f-9076-bd251b55a9ee` |
| `attempt_id` | `550d4a64-0306-5f15-a0ab-f65722c790a2` |
| `claim_id` | `8a3ba04b-6548-577f-9773-2b30744b929f` |
| `launch_reservation_id` | `51e87e09-cea2-5828-8598-14dd053be048` |
| `launch_execution_id` | `f5727d7d-dd0b-50d8-8bf3-6ff2e44414e7` |
| `terminal_id` | `bfee46cc-85a7-5fa7-88cd-0d5468dc51ef` |
| `selection_id` | `f10c3fc1-49b0-554a-8fa7-d36fa4d1bee8` |
| `recovery_id` | `9aaadbb2-62af-58db-af21-b5208551ec01` |

The retained migration vector is:

```text
authority_epoch_id       = 12345678-1234-5678-9abc-def012345678
schema_version           = 3
migration_policy_version = migration-policy/v1
framed UTF-8 preimage    = 15:migration_id/v136:12345678-1234-5678-9abc-def0123456781:319:migration-policy/v1
migration_id             = b1114fec-2247-506d-bfda-74008355b312
```

Administrator-provisioned `machine_authority_id`, `authority_epoch_id`, and
`signing_key_id` remain signed authority/key facts. Child references such as
`attempt_id` on a claim are foreign-key references, not a second identity
tuple. There is no `allocation_id` identity or identity material in this
model.

## 6. Transaction boundaries and crash outcomes

All writes in the fixture harness use one local SQLite database and
`BEGIN IMMEDIATE`. The service verifies the fixed bootstrap/epoch/schema before
opening the session-creation transaction, then reconciles metadata and request
descriptor semantics before canonicalization, identity derivation, or session
insertion. Uncommitted work rolls back; committed evidence is never repaired
by deleting rows.

The required order is:

```text
fixed bootstrap/CNG/ACL/path verification
  -> session BEGIN IMMEDIATE
  -> read singleton metadata and reconcile the exact public Alpaca descriptor
  -> canonical request bytes, digest, session identity, insert, and COMMIT
  -> attempt ordinal transaction
  -> permanent claim transaction and COMMIT
  -> credential/provider/network construction
  -> launch reservation transaction and COMMIT
  -> CreateProcessW(CREATE_SUSPENDED)
  -> Job Object and process evidence transaction and COMMIT
  -> resume intent transaction and RESUME_INTENT_COMMITTED COMMIT
  -> external ResumeThread through the reviewed adapter using the one-shot permit
  -> exact canonical successful resume receipt returned to the transaction service
  -> paired post-resume and cleanup evidence transaction and COMMIT
  -> terminal matrix validation and immutable terminal transaction
  -> execution/reservation/attempt terminal-recorded transitions in that transaction
  -> explicit successful session selection
```

The claim commit precedes all credential/provider/network construction. The
claim insertion itself is the session-wide admission point: the authoritative
trigger rejects every prior outcome except the exact digest-valid
process-creation-failure `FAILED`/`NOT_STARTED` lineage with no execution. The
helper does not run an ad hoc unresolved-execution query.

The reservation commit precedes process creation. The `PRE_RESUME_READY`
execution row commits process, Job Object, and resume-authorization evidence.
A separate `BEGIN IMMEDIATE` transaction then appends the canonical intent and
commits `RESUME_INTENT_COMMITTED`; only that winner receives the one-shot
permit accepted by the reviewed adapter. The adapter observes that committed
state, performs the modeled external call once, and returns the exact canonical
success receipt bound to the execution and intent digest. Only then may the
transaction service persist the receipt as post-resume evidence, persist
cleanup evidence, verify both digests, and advance the execution to
`RESUME_RECORDED`. SQLite enforces the durable one-reservation and one-intent
fences, exact persisted bytes, and phase rules; it cannot prove that an
external Windows API call occurred.

A crash after a claim or reservation commit leaves that fence consumed. A
crash before resume-intent commit leaves `PRE_RESUME_READY`, where the separate
conservative pre-intent recovery action remains available. Once intent commits,
neither a second intent nor another `ResumeThread` attempt may be authorized.
A crash immediately after intent commit but before the call and a crash after
the call but before receipt persistence both leave exactly
`RESUME_INTENT_COMMITTED` with no receipt, cleanup, or terminal. The service
must treat both as unresolved/manual, never reconstruct the permit, never
retry the hook, never create another claim or intent, and never relabel the
outcome `NOT_STARTED`. A known process-creation failure is recorded on the
existing reservation and may receive a terminal without an execution row.

The only recovery for that exact unresolved resume window is
`CLASSIFY_RESUME_OUTCOME_UNKNOWN`. In one `BEGIN IMMEDIATE` transaction it
verifies the normalized lineage and digest-valid pre-resume plus intent evidence, appends
the recovery at the current session recovery ordinal, advances that counter
exactly once, and changes the reservation from `PROCESS_CREATED` to
`MANUAL_REVIEW` while preserving its original outcome timestamp and leaving
the execution unchanged. It may then be recorded as
`CLOSED`/`MAY_HAVE_OCCURRED` and the session may be closed under the normal
close policy. It cannot produce `NOT_STARTED` or authorize another side
effect.

The whole-boundary audit treats every arrow from claim commit through
selection as an authority handoff: claim commit -> provider construction ->
reservation commit -> `CreateProcessW` -> `PRE_RESUME_READY` commit -> resume
intent commit -> `ResumeThread` -> exact receipt/evidence commit -> terminal
-> selection. Positive, rejection, two-connection concurrency, and crash
cases cover each handoff. Exactly one reservation fences process creation;
exactly one committed intent and its opaque winner permit fence
`ResumeThread`; and only the exact intent-bound `RESUMED` receipt can prove
modeled success and unlock a successful terminal. Every uncertainty path
remains claim-blocking. The canonical request bytes propagated through the
lineage and the UUID5 identity material describe the same validated request
semantics; alternate representations never reach either boundary.

Manual recovery records uncertainty and an operator-authorized classification
through the closed action matrix above. It does not turn uncertainty into
`NOT_STARTED`, manufacture normal workflow states, erase a claim, reopen a
reservation, or infer a successful selection. `SELECT_COMMITTED_SUCCESS` is the
only recovery action that invokes normal selection authority, and it still
requires the successful terminal matrix entry.

## 7. SQLite durability and rollback contract

The production deployment must use the reviewed local NTFS SQLite build with
foreign keys enabled, one database scope, `PERSIST` journaling, and
`synchronous=FULL`. The database and persistent journal are provisioned in
advance and validated against the exact Trading ACL. No runtime `ATTACH`,
`VACUUM`, automatic migration, journal-rights workaround, database replacement,
or legacy file fallback is allowed.

The test-only fixture proves schema execution, `foreign_key_check`, integrity
checks, parent keys, unique fences, trigger behavior, concurrency, and rollback.
Windows provisioning and durability acceptance remain future manual gates.

Administrator backups are consistent SQLite online backups or fully quiesced
reviewed copies of the database/journal. A separate signed
`backup_manifest/v1` binds database/journal digests to generation, epoch,
schema, release, and purpose. A bootstrap signature is not a backup-manifest
signature. Restore validation is historical-only and requires a new signed
generation/epoch plus a new empty executable database.

Schema-1 and schema-2 file artifacts remain parseable historical evidence only.
They cannot be imported as claims, selected as authority, or used as a
fallback when SQLite is unavailable.

## 8. Design evidence and future milestones

The focused executable evidence is
`tests/runtime/test_windows_transactional_capture_authority.py`. It covers:

- complete DDL execution, `foreign_key_check`, integrity, FK parent keys, and
  prohibited ancestor columns;
- the metadata/migration/session/attempt/claim/reservation/execution/terminal
  lifecycle and terminal selection;
- one-to-one fences and same-session selection/recovery lineage;
- deterministic identity vectors;
- exact public Alpaca descriptor sourcing, metadata/request reconciliation,
  drift rejection before persistence, and regenerated descendant vectors;
- exact session-to-immediate-parent request propagation and mismatch rejection;
- the complete terminal state/disposition matrix and append-only paired launch
  evidence rules;
- the authoritative session-wide claim-admission matrix through both helper
  and direct insertion, including the sole retry-safe prior lineage;
- reservation-only `COMMITTED` insertion, first-outcome timestamp preservation,
  and write-once session close facts;
- attempt and recovery ordinal races, stale/future ordinals, direct-counter
  rejection, rollback atomicity, and independent session ordinals;
- the closed recovery action matrix, including distinct-target races and
  table-driven invalid lifecycle transitions;
- a process-creation failure terminal without an execution row, plus the
  conservative unknown-resume recovery and close path; and
- fake side-effect hooks proving claim, reservation, pre-resume, external
  resume, post-resume, and terminal ordering; receipt binding; and no new
  claim after an unresolved resume outcome.

The following remain future production milestones:

1. implement the fixed Windows bootstrap, CNG verification, ACL, reparse,
   final-handle, SID, and local-volume checks;
2. implement the reviewed transaction service against this schema without
   introducing denormalized ancestor columns;
3. implement the child credential/provider/process boundary and sanitized
   evidence adapters;
4. perform administrator backup/restore and dedicated-account Windows
   acceptance; and
5. separately approve or reject any unattended scheduler design.

Until those gates pass, this is test-only research infrastructure. No real
credentials, real provider calls, brokerage calls, or real-money orders are
used or authorized.
