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
`CLOSED` also requires close facts. Session identity and request evidence are
immutable.

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

### 2.5 provider_call_claims

Claims reference only `attempt_id`, which is `NOT NULL UNIQUE` and references
`attempts(attempt_id)`. The table stores the permanent `COMMITTED` state,
claim schema/policy, provider/operation/budget, request/digest bindings,
immutable claim evidence, and commit timestamp. It has no session, epoch,
ordinal, or allocation columns. Claim rows cannot be updated or deleted.

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

### 2.7 launch_executions

Executions reference only `launch_reservation_id`, which is `NOT NULL UNIQUE`
and references `launch_reservations(launch_reservation_id)`. They store
process-creation, Job Object, resume-authorization, phase, post-resume, and
cleanup evidence. The phase moves forward through
`PRE_RESUME_READY`, `RESUME_RECORDED`, `POST_RESUME_AMBIGUOUS`,
`TERMINAL_RECORDED`, and `CLOSED`. Execution evidence is immutable except for
these explicitly controlled phase/evidence additions. An execution is
optional: a process-creation failure may still receive a terminal directly
from its reservation.

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
`NOT_STARTED`. Terminal rows are immutable and cannot be deleted.

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
counter, a non-empty state change, and a target that resolves through the
immediate-parent chain to that same session. The `AFTER INSERT` trigger owns
the exact counter increment. The reviewed test transaction service validates
the action, operator evidence, target state, and authorized state update in the
same `BEGIN IMMEDIATE` transaction. Recovery never deletes or reopens a claim
or reservation, never authorizes another provider call, and is rejected after
an absorbing session state.

## 3. Enforcement split

The fixture deliberately enforces only facts that SQLite can evaluate at the
row boundary. The reviewed transaction service and transaction tests enforce
the multi-statement semantic contract.

| SQLite schema, constraints, and triggers | Reviewed transaction service/tests |
| --- | --- |
| Immediate-parent foreign keys and `foreign_key_check` integrity | Workflow ordering across multiple statements and tables |
| Append-only immutable evidence and prohibited deletes | Canonical request construction, digest reconciliation, and policy reconciliation |
| One-to-one claim, reservation, execution, terminal, selection, and ordinal fences | Action-specific recovery authorization and operator evidence |
| Unique per-session ordinals and trigger-owned exact increments | Commit-before-side-effect boundaries |
| Valid local monotonic state transitions and locally provable absorbing states | Complete transaction atomicity and crash classification |
| Typed recovery target existence and same-session lineage | Cross-table semantic rules that would otherwise require copied ancestor columns |
| Digest lengths, fixed enum values, provider budget, and typed success facts | UUID5 identity computation and comparison against the reviewed contract |

SQLite does not authenticate executables, inspect Windows ACLs, verify CNG
signatures, read Credential Manager, validate provider responses, or protect
against malicious direct SQL from compromised trusted-token code. Complex
triggers are not added for that excluded threat.

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
read sessions.next_recovery_ordinal
validate target and authorized transition
perform any allowed target-state update in this transaction
INSERT exactly one manual_recoveries row
-- no independent counter UPDATE
COMMIT
```

The `BEFORE INSERT` trigger validates open-session eligibility, the current
ordinal, supported target kind, same-session target lineage, and a non-empty
state change. The `AFTER INSERT` trigger performs the sole exact counter
increment. Its guard uses the immutable recovery row at the old counter and
the committed per-session row count to reject direct updates, no-ops,
regressions, skips, second increments, and unpaired writes. Recovery rows
cannot be updated or deleted.

The trigger cannot and does not attempt to express the complete deferred
workflow. The reviewed transaction service, not an impossible deferred
SQLite trigger, enforces the action-specific policy and complete atomic
multi-statement state transition.

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
| `session_id` | `e5179727-d0f1-5eac-8c01-2e2105a1a9c1` |
| `attempt_id` | `be483fa1-abe3-5721-90bc-84868cf3dd19` |
| `claim_id` | `6ec45116-d8a8-50ea-8d94-7ac47329c7e9` |
| `launch_reservation_id` | `222adedb-e4e7-5bbc-acc2-e7022a1785ac` |
| `launch_execution_id` | `4ce95417-de13-569f-923b-e17d2d9854c6` |
| `terminal_id` | `5fda0305-878a-550f-b724-a7ce775e6a30` |
| `selection_id` | `77b12359-7413-536c-a03c-d6604588aee1` |
| `recovery_id` | `40eff555-9402-598d-868c-e0ad8776249e` |

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
`BEGIN IMMEDIATE`. The service verifies the fixed bootstrap/epoch/schema and
canonical request before authority mutation. Uncommitted work rolls back;
committed evidence is never repaired by deleting rows.

The required order is:

```text
fixed bootstrap/CNG/ACL/path verification
  -> canonical request and digest reconciliation
  -> session transaction
  -> attempt ordinal transaction
  -> permanent claim transaction and COMMIT
  -> credential/provider/network construction
  -> launch reservation transaction and COMMIT
  -> CreateProcessW(CREATE_SUSPENDED)
  -> Job Object and process evidence transaction and COMMIT
  -> ResumeThread
  -> post-resume evidence or conservative ambiguity
  -> immutable terminal transaction
  -> explicit successful session selection
```

The claim commit precedes all credential/provider/network construction. The
reservation commit precedes process creation. Launch evidence commits before
resume authorization. A crash after a claim or reservation commit leaves that
fence consumed. A crash after resume is ambiguous even when no child result is
present; it never authorizes a new claim, provider call, reservation, or
launch attempt. A known process-creation failure is recorded on the existing
reservation and may receive a terminal without an execution row.

Manual recovery records uncertainty and an operator-authorized classification;
it does not turn uncertainty into `NOT_STARTED`, erase a claim, reopen a
reservation, or infer a successful selection.

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
- attempt and recovery ordinal races, stale/future ordinals, direct-counter
  rejection, rollback atomicity, and independent session ordinals;
- a process-creation failure terminal without an execution row; and
- fake side-effect hooks proving claim, reservation, and evidence commit
  boundaries plus no claim reuse after ambiguity.

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
