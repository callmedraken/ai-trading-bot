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

### Inter-process lifecycle arbitration contract

Every launch-reservation boundary that can dispatch an external effect, persist
its result, or classify the same uncertainty uses one deterministic OS-backed
inter-process lifecycle arbiter. A Python `threading.RLock`, a process-local
lock dictionary, and SQLite writer serialization are not lifecycle authority:
they cannot exclude another approved process between the final lineage check
and a Windows call.

The arbiter key is SHA-256 over the exact canonical UTF-8 JSON object below,
using sorted keys and no insignificant whitespace:

```json
{"authority_epoch_id":"<epoch UUID>","label":"lifecycle-arbiter/v1","launch_reservation_id":"<reservation UUID>","machine_authority_id":"<machine UUID>"}
```

The lowercase 64-character digest, never a raw identifier, is the bounded
object-name suffix. Lifecycle authority is machine-scoped, not scoped to an
interactive Windows session. Milestone A production uses the fixed global
Windows object namespace
`Global\\AITradingBot-Lifecycle-v1-<digest>`. Every Trading worker,
scheduler/helper, recovery process, and approved administrator tool opens that
same named mutex regardless of its Windows session. `Local\\` is prohibited
for lifecycle arbitration. The fixed `Global\\AITradingBot-Lifecycle-v1-`
prefix and digest-derived suffix are not caller selectable.

Creation and opening use the administrator-reviewed security descriptor. For
the lifecycle mutex only, the approved owner is exactly
BUILTIN\\Administrators, LOCAL SYSTEM, or the exact signed/verified Trading
SID; filesystem authority objects remain owned by BUILTIN\\Administrators.
The DACL admits only the approved administrator and Trading principals
required by this architecture and denies untrusted creation, replacement, or
synchronization. An existing object with an unexpected type, ownership, DACL,
name, or other security property causes fail-closed startup; there is no
fallback to `Local\\` or a differently named mutex. Neither a caller nor
database content selects another namespace, prefix, security descriptor, lock
path, timeout, lease, or heartbeat. Lock stealing, timeout takeover, and
session-local fallback are prohibited.

The executable harness uses a same-key advisory file lock below one fixed,
process-independent adapter root resolved from the harness module's checked-out
repository location:
`<repository-root>/.pytest_cache/ai-trading-bot-lifecycle-arbiters-v1/<digest>.lock`.
The module resolves and validates that absolute root once. `TEMP`, `TMP`,
`TMPDIR`, current directory, caller input, PID, thread identity, and
per-process random state cannot select or split the adapter namespace; only the
digest suffix varies by reservation authority identity. Cooperating processes
from the same checkout therefore contend on the same path, while different
reservation identities select different lock files. Lock files are not deleted
as test cleanup while another process may own them.

That repository-anchored directory is ignored test infrastructure only. It is
not a production ACL/security boundary and is not included in the lifecycle
identity digest. The adapter validates inter-process exclusion and
process-death release semantics only. Milestone A production continues to use
the secured machine-wide
`Global\\AITradingBot-Lifecycle-v1-<digest>` named mutex with the unchanged
canonical digest material. This PR does not implement the production Windows
mutex, namespace validation, privilege or ACL provisioning, DACL enforcement,
or real Windows acceptance; those remain Milestone A work.

The global acquisition order is mandatory:

1. derive the reservation identity from already validated immutable input;
2. acquire the OS lifecycle arbiter while no SQLite transaction is active;
3. open or use the SQLite connection and re-resolve the complete durable active
   lineage;
4. for durable changes, execute and commit one `BEGIN IMMEDIATE` transaction;
5. for provider construction, `CreateProcessW`, or `ResumeThread`, perform the
   external call with no SQLite transaction open while retaining the arbiter;
6. release the arbiter only after typed result production or durable commit.

Code must never wait for the arbiter while holding `BEGIN IMMEDIATE`, and must
never hold an SQLite write transaction across an external call. This order is
the single lock hierarchy; there is no nested lifecycle arbiter.

Any authority operation that acquires the OS-backed lifecycle arbiter MUST
reject an active transaction on every SQLite connection that the operation
will use for authority or lineage observation, whether the connection is a
method argument or stored on an adapter. The rejection occurs before
capability or registry lineage resolution that selects the arbiter, arbiter
construction or acquisition, SQLite queries, capability consumption, event
emission, or an external effect. The transaction service, not its caller, owns
the SQLite transaction nested beneath the arbiter. A caller cannot wrap
process-intent, process-result, resume-intent, resume-result, terminal, or
reservation-classification recovery work in an outer SQLite transaction. A
`SAVEPOINT` does not make reversed acquisition legal. Rejection is immediate
and does not query authority state, consume a capability, emit an external
event, mutate a row, or silently commit, roll back, or otherwise alter
caller-owned work; the caller must explicitly end its transaction before
retrying the unchanged lifecycle boundary.

The production external-boundary contract does not require provider
construction, `CreateProcessW`, or `ResumeThread` APIs to receive a
caller-owned SQLite connection. Each boundary nevertheless enters the arbiter
with no pre-existing SQLite transaction, performs its final lineage observation
beneath the arbiter, and leaves no SQLite transaction open across the external
effect. The executable `FakeSideEffects` adapter holds a persistent exact
`sqlite3.Connection` as `self.observer`; therefore each of its three public
external methods explicitly rejects `self.observer.in_transaction` before
registry resolution or arbiter construction. After the caller explicitly
rolls back, an unchanged valid capability remains usable exactly once only
while its durable lineage is still active.

Private issuers, one-shot objects, and their registries are process-local
provenance checks only. They are never serialized, pickled, transferred,
reconstructed, or reissued in another process and are not substitutes for the
OS arbiter. Process death destroys every unpersisted capability. A restarted
process must reconcile durable SQLite state and choose the documented recovery;
it must not recreate a permit from public fields.

Each registry stores an immutable private issuance record containing the exact
issued object, its one-shot token and issuer, and its original reservation and,
where applicable, execution identity. Caller-visible object attributes are
validated copies, not authority for choosing an arbiter, database lineage, or
event attribution. Every capability boundary resolves and validates the exact
registry record before arbiter selection, uses only registry-side identities,
and rechecks the record before consumption. This remains fail-closed even if a
caller bypasses frozen-field assignment with reflective mutation.

Normal owner exit and abrupt process termination release the OS object. In
production, `WAIT_ABANDONED` is conservative evidence that the prior owner died,
not evidence that a provider or Windows API call did or did not occur. The new
owner retains the mutex, rechecks durable state, emits no automatic retry, and
maps `COMMITTED` to `CLASSIFY_LAUNCH_RESERVATION`,
`PROCESS_INTENT_COMMITTED` to `CLASSIFY_PROCESS_OUTCOME_UNKNOWN`, and an
unreceipted `RESUME_INTENT_COMMITTED` execution to
`CLASSIFY_RESUME_OUTCOME_UNKNOWN`. Definitive persisted results continue by
their recorded state. The test file-lock adapter proves release and
reconciliation after process death but cannot expose Windows
`WAIT_ABANDONED` or validate the production DACL.

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
  reviewed database/journal and capture-output rights. The concrete
  database/journal mask includes `FILE_WRITE_EA` because the standard Windows
  SQLite VFS requests `GENERIC_WRITE`; this bit does not grant DELETE,
  WRITE_DAC, WRITE_OWNER, or parent-directory replacement authority.
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

The signed bootstrap and immutable metadata also select the authority and
claim policy versions. This release implements exactly
`authority-policy/v1` and `claim-policy/v1`. A signed alias, casing variant,
legacy value, or unknown future version is not forward-compatible authority:
the release fails closed rather than execute policy semantics it does not
implement.

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

The insert contract is exact: a session begins `OPEN`, both ordinal counters
are zero, and both close facts are null. No direct insert may begin selected,
closed, at another state, with a consumed ordinal, or with pre-populated close
facts. Only forward session transitions are permitted. `SUCCESS_SELECTED` and
`CLOSED` are absorbing with respect to selection/recovery eligibility;
`CLOSED` also requires both `closed_at_utc` and `close_reason`. Those facts
must both be null before closure, may be populated exactly once while moving
`OPEN` to `CLOSED` under `CLOSE_SESSION` or moving a selection-backed
`SUCCESS_SELECTED` session to `CLOSED`, and cannot thereafter be replaced,
cleared, partially changed, or changed by a same-state `CLOSED` update. Session
identity and request evidence are immutable.

Caller-owned request dictionaries and lists are untrusted mutable inputs. The
transaction service first requires an exact dictionary, copies its top-level
fields once, captures `ordered_universe` into a new tuple, validates only those
captured values, and returns one frozen, slots-backed
`ValidatedCaptureRequest`. The snapshot contains the exact ten semantic fields
and no reference to the caller's dictionary or list. After it exists, no
session operation may read the caller-owned objects again.

Session creation reconciles that immutable snapshot before canonicalization or
identity derivation. In one `BEGIN IMMEDIATE` transaction, the reviewed service
reads the singleton `authority_metadata` row, verifies its provider and
operation exactly match `ALPACA_DAILY_SNAPSHOT_DESCRIPTOR`, verifies
`authority_policy_version=authority-policy/v1` and
`claim_policy_version=claim-policy/v1` exactly, and validates one exact
`capture_request/v2` object. Unsupported signed policy is rejected in that
transaction before request canonicalization, `session_id` derivation, or
insertion. Its key set is exactly
`bar_interval`, `child_operation_version`, `ordered_universe`,
`output_policy_version`, `permitted_provider_operation`, `provider_id`,
`request_limit`, `request_window_end_date`, `request_window_start_date`, and
`target_session_date`; no key is optional and no unknown key is accepted.

Every captured scalar string has exact string type. The caller's
`ordered_universe` has exact list type; the snapshot stores a newly allocated
`tuple[str, ...]`. It is nonempty and contains at most the public
`MAX_DAILY_SNAPSHOT_SYMBOLS` bound. Every entry has exact string type and is
validated through the public `trading_bot.domain.Symbol`. The authority
computes `canonical_text = str(Symbol(entry))` and requires
`entry == canonical_text` exactly. It does not trim, uppercase, or otherwise
normalize an alias. Lowercase, padded, blank, over-ten-character, and
unsupported-punctuation forms fail closed; canonical uppercase letters,
periods, and hyphens remain accepted. Duplicate detection uses the canonical
Symbol strings, so normalization-equivalent entries cannot evade it. A tuple
or other caller iterable is not equivalent to the required input list.
`request_limit` has exact positive integer type (a boolean is not an integer
for this contract), equals the universe length, and does not exceed the same
bound. The three dates are exact canonical `YYYY-MM-DD`; the request window
start is no later than its end, and its end is strictly before the target
session date. `bar_interval=1d`, `child_operation_version=child/v1`,
`output_policy_version=output/v1`, and the provider/operation from the public
descriptor are fixed byte-for-byte. Metadata and request descriptor values
must also agree.

Only after every snapshot shape, type, Symbol, bound, date, fixed-value,
metadata, and descriptor check succeeds may the service call the snapshot's
single canonical serialization method, derive `session_id` from that same
snapshot, read `target_session_date` from it, and insert using only those
snapshot facts. Serialization recreates the established JSON object and emits
`ordered_universe` as a JSON list, so valid request bytes and UUID5 vectors do
not change. A caller mutation after snapshot creation cannot desynchronize
JSON, digest, identity material, target date, or insertion. Rejection leaves
no session, counter, attempt, claim, reservation, execution, terminal,
selection, or recovery side effect. Invalid alternate representations cannot
enter storage or exploit an identity collision with a valid request. Existing valid request
bytes and UUID5 vectors remain unchanged.

The `sessions_before_insert` trigger independently admits only one exact
canonical UTF-8 JSON BLOB representation of `capture_request/v2`. Native JSON1
checks require the exact ten-field object, exact JSON types and fixed values,
canonical bounded duplicate-free Symbol text, canonical date-only values and
ordering, the request limit/universe relationship, and exact canonical bytes
before validating the digest. The trigger also binds the embedded target date
to `sessions.target_session_date`, binds the embedded provider and operation to
the exact public descriptor values in the referenced metadata row, and
enforces the canonical initial state and copied policies. This protects the
persisted boundary from cooperating direct SQL while the service gate remains
responsible for snapshotting mutable caller input, invoking public `Symbol`,
deciding which signed versions the release supports, and deriving UUID5
identities. Each request date-only field uses the same explicit integer
Gregorian month/day/leap-year arithmetic as timestamp v1, without relying on
SQLite date/time parser normalization.

The session row is the sole canonical request owner. Attempts and claims copy
its exact bytes and digest through immediate-parent checks; reservations and
terminals retain that digest lineage. Descendants neither reconstruct nor
independently reinterpret the request. UUID5 generation remains service-owned
and unchanged.

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

The session is the sole canonical request owner. Only the validated immutable
snapshot constructs the canonical request bytes used by session creation.
Attempt allocation reads
those exact stored bytes/digest, authority and claim policy values from the
session, and provider/operation from the session's metadata lineage; it does
not reconstruct the request or substitute release constants. The
`attempt_id/v2` helper receives the persisted provider, operation, and claim
policy explicitly, and `attempt_policy_version` is the owning session's claim
policy. The attempt insert trigger uses the normalized
`attempt -> session -> metadata` path to reject request, claim-policy,
provider, or operation drift.

### 2.5 provider_call_claims

Claims reference only `attempt_id`, which is `NOT NULL UNIQUE` and references
`attempts(attempt_id)`. The table stores the permanent `COMMITTED` state,
claim schema/policy, provider/operation/budget, request/digest bindings,
immutable claim evidence, and commit timestamp. It has no session, epoch,
ordinal, or allocation columns. Claim rows cannot be updated or deleted.

Claim creation reads the exact provider, operation, budget, policy, request
bytes, and digest from its immediate attempt parent. `claim_id/v2` receives
those persisted attempt values explicitly, and the inserted claim policy must
equal `attempt_policy_version`; no module default can reset it. The authoritative
`provider_call_claims BEFORE INSERT` trigger resolves the normalized
`claim -> attempt -> session` path and admits a claim only when the owning
attempt is `ALLOCATED`, its session is `OPEN`, the inserted claim is
`COMMITTED` with exact immediate-parent bindings, the session has no
selection or successful-but-unselected terminal, and every already-committed
claim in that session has the one retry-safe prior outcome.

That sole retry-safe outcome is an attempt in `TERMINAL_RECORDED` whose claim
has one reservation in `TERMINAL_RECORDED`, immutable SHA-256-valid
process-intent and process-creation-failure evidence, a
`FAILED`/`NOT_STARTED` terminal without a snapshot, and no `launch_execution`.
All other prior lineages block: no reservation; `COMMITTED`;
`PROCESS_INTENT_COMMITTED`; `PROCESS_CREATION_FAILED` without its terminal;
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
evidence, append-only process-intent evidence, controlled reservation outcome,
process-creation-failure evidence, and timestamps. They have no session,
attempt, allocation, or epoch columns.

`COMMITTED` is the conservative reservation-only state before process authority
is allocated. The controlled sequence is `COMMITTED ->
PROCESS_INTENT_COMMITTED -> PROCESS_CREATED | PROCESS_CREATION_FAILED |
MANUAL_REVIEW`, followed where valid by `TERMINAL_RECORDED`. The separate
`COMMITTED -> MANUAL_REVIEW` recovery path remains available before an intent
exists. There is no reclamation, expiry, replacement, or second reservation or
intent path.

Reservation creation reads the exact request digest from its immediate claim
parent, its claim policy from that claim, and authority policy from the
normalized `claim -> attempt -> session` lineage. Reservation identity and row
values receive those persisted facts explicitly. The reservation insert
trigger verifies the request, claim-policy, and session-authority-policy
bindings and requires every inserted reservation to start exactly in
`COMMITTED`, with process-intent, process-creation-failure, and outcome facts
all null.

The unique reservation is also the durable claim-to-provider handoff fence.
Only the transaction that inserts it receives an exact frozen, slots-backed
`FakeProviderConstructionPermit`; it is not a string subtype and has one
reservation field, a private issuer, and a registered one-shot permit. The
registry independently freezes the exact issued object and original
reservation binding. The permanent claim alone, an existing reservation,
restart state, copied or reconstructed objects, mutated visible fields, and
wrong issuers or permits cannot recreate or redirect this authority.

Provider construction first rejects an active transaction on the executable
fake's stored observer, then resolves the original reservation from the exact
registry entry. Under the OS-backed inter-process lifecycle arbiter it queries
the normalized reservation -> claim -> attempt -> session lineage: reservation
`COMMITTED` with no process intent,
claim `COMMITTED`, attempt `LAUNCH_RESERVED`, session `OPEN`, no execution,
terminal, or selection, and exact request/provider/operation/budget/policy
evidence. It consumes the permit immediately before the modeled construction
event and holds the arbiter through production of one exact typed
`FakeConstructedProvider`; no SQLite transaction spans construction. A modeled
failure returns no capability. Recovery, process-intent commitment, terminal
recording, selection, or closure revokes an outstanding permit.

`commit_process_intent(connection, reservation_id, constructed_provider) ->
FakeProcessIntent` requires the exact privately issued, registered, one-shot
`FakeConstructedProvider` for the same reservation and owns
the one-shot `CreateProcessW` fence. In one `BEGIN IMMEDIATE` transaction it
requires exactly `COMMITTED`; verifies the claim state, request bytes/digests,
claim and reservation evidence digests, provider operation and budget, and
authority/claim policy lineage; appends one exact canonical intent; records its
SHA-256 digest and commit timestamp; advances to
`PROCESS_INTENT_COMMITTED`; commits before any process hook; and only then
consumes the constructed-provider capability:

```json
{"authority_policy_version":"<authority policy>","claim_policy_version":"<claim policy>","launch_reservation_id":"<reservation id>","process_operation":"CreateProcessW","request_digest":"<lowercase hex>","schema":1}
```

A transient process-intent rollback while the lineage remains active preserves
that exact capability for one retry. A crash after reservation commit but
before construction, a modeled construction failure, or loss of the
constructed-provider capability before process-intent commit leaves
`COMMITTED` and permits only `CLASSIFY_LAUNCH_RESERVATION`; construction and
capability reconstruction are never retried.

Only the winning transaction receives an opaque in-memory `FakeProcessIntent`.
Under the OS-backed inter-process lifecycle arbiter, the external adapter
accepts only the exact registered object, private issuer, and permit; resolves the normalized
reservation -> claim -> attempt -> session lineage; requires
`PROCESS_INTENT_COMMITTED`, `COMMITTED`, `LAUNCH_RESERVED`, and `OPEN` with no
terminal or selection; verifies the durable canonical bytes/digest; and consumes
the permit immediately before the modeled call. The arbiter remains held through
typed result production but no SQLite transaction remains open across the call.
A second acquisition, copied or reconstructed object, wrong permit,
cross-reservation use, permit reuse, and delayed dispatch after recovery fail
before the modeled external call. SQLite proves the durable ownership decision,
not that Windows executed `CreateProcessW` or that no call is already in flight.

The adapter returns either an exact typed `FakeProcessCreationReceipt` for a
suspended child with Job Object setup and resume authority, or an exact typed
`FakeProcessCreationFailure` whose sole outcome is `NOT_CREATED`. Each result
binds the reservation and committed intent digest, carries canonical schema-1
bytes plus SHA-256 digests, and has a private adapter issuer plus a registered
one-shot result permit. Under the same lifecycle arbiter, `record_execution`
and `record_process_creation_failure` recheck the complete active lineage in a
`BEGIN IMMEDIATE` transaction and accept only the exact registered adapter
object. They consume its result permit only after commit. A transient rollback
while the lineage remains active leaves the original result registered and
retryable; recovery, terminal recording, selection, or closure instead revokes
it permanently. Missing, malformed, noncanonical, copied, reconstructed,
wrong-issuer, wrong-permit, wrong-intent, cross-reservation, and reused results
fail closed. Application helpers cannot fabricate process results. Canonical
bytes and digests prove content integrity, not adapter provenance.

A known process-creation failure is a one-time
`PROCESS_INTENT_COMMITTED -> PROCESS_CREATION_FAILED` update with matching
canonical failure evidence and a non-null outcome timestamp. The intent and
failure facts cannot be replaced, cleared, or partially written. This remains
the only path to a retry-safe `FAILED`/`NOT_STARTED` terminal.

`outcome_recorded_at_utc` records the first post-reservation outcome. It moves
from null to a value exactly once on the first transition to
`PROCESS_CREATED`, `PROCESS_CREATION_FAILED`, or `MANUAL_REVIEW`. Committing a
process intent leaves it null. Every later transition, including
`PROCESS_CREATED -> MANUAL_REVIEW` and
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
Execution creation reads `application_release_version` and
`authority_policy_version` from its reservation and passes both explicitly to
`launch_execution_id/v2` and the row. A normalized parent-policy trigger
rejects a direct insert that changes either copied fact or lacks a digest-valid
`PROCESS_INTENT_COMMITTED` immediate parent. Execution evidence is copied only
from the exact successful adapter receipt.

`commit_resume_intent(connection, execution_id) -> FakeResumeIntent` owns the
one-shot resume fence. In one `BEGIN IMMEDIATE` transaction it resolves the
normalized execution -> reservation -> claim -> attempt -> session lineage,
requires the session to be `OPEN`, the reservation to be `PROCESS_CREATED`, no
terminal or session selection, and exactly `PRE_RESUME_READY`, and verifies the
process-creation, Job Object, and resume-authorization JSON/digest pairs. Its
guarded update repeats that entire active-lineage predicate before appending
this exact canonical evidence and committing the phase change:

```json
{"execution_id":"<exact execution_id>","resume_operation":"ResumeThread","schema":1}
```

Only the transaction winner receives the opaque, typed in-memory permit.
Intent JSON, digest, and timestamp are one append-only triple: a second intent,
standalone field write, direct phase jump, clearing, replacement, reassignment,
or use for another execution fails closed. The permit is consumable once and
is not reconstructible from the database after restart. This durable intent is
the authority fence; it does not prove that Windows executed `ResumeThread`.
The permit is necessary but never sufficient authority: every later use must
still prove the same active lineage. `MANUAL_REVIEW`, any terminal-recorded
lineage, `SUCCESS_SELECTED`, and `CLOSED` are irreversible revocation barriers
for all outstanding or delayed resume authority.

The fake external boundary accepts only that exact registered
`FakeResumeIntent`, then under the
OS-backed inter-process lifecycle arbiter immediately re-resolves and rechecks the
complete normalized active lineage, committed canonical intent, and all
pre-resume evidence. It consumes the permit only after those checks and returns
a privately issued, registered one-shot receipt only after the modeled call
succeeds. A modeled failure creates no receipt and leaves the database at
`RESUME_INTENT_COMMITTED`. The successful receipt body is exactly canonical
UTF-8 JSON; its bytes and digest prove content integrity but cannot reconstruct
adapter provenance:

```json
{"execution_id":"<exact execution_id>","resume_intent_digest":"<lowercase 64-character SHA-256 hex>","resume_result":"RESUMED","schema":1}
```

`record_post_resume_evidence` runs under the same lifecycle arbiter and in one
`BEGIN IMMEDIATE` transaction. It re-resolves the full normalized active
lineage both before and in its guarded update, so a structurally successful but
delayed receipt cannot advance a reservation classified by recovery or a
lineage already terminal, selected, or closed. It requires exact
`FakeResumeReceipt` type, private adapter issuer, the exact registered and
unconsumed result permit, the
same execution and committed intent digest, exact field set and field types,
integer schema `1`, literal `RESUMED`, exact canonical bytes, and the exact
SHA-256 digest. `FAILED`, `ERROR`, `UNKNOWN`, missing/extra fields, wrong or
string schema, noncanonical bytes, wrong execution/intent/digest, receipt
reuse, and cross-execution reuse all fail. Only one
`RESUME_INTENT_COMMITTED -> RESUME_RECORDED` transaction may append that
receipt and the complete cleanup pair. The result permit is consumed only
after that transaction commits. Validation or transient database rollback
while the parent remains active preserves the original issued receipt for an
exact retry; a persisted revocation leaves it structurally valid but unusable.
Intent, post-resume, and cleanup
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
snapshot digest matches. `selected_at_utc` must be greater than or equal to the
`recorded_at_utc` of that exact referenced terminal; a newer terminal in
another lineage is irrelevant. The application transaction then commits the
selection and the session/attempt success transitions together.

### 2.10 manual_recoveries

Recoveries are direct session children with `recovery_id`,
`recovery_ordinal`, `target_kind`, and `target_id`. `target_kind` is exactly
one of `SESSION`, `ATTEMPT`, `CLAIM`, `LAUNCH_RESERVATION`, and `TERMINAL`.
There are no five nullable target columns and no copied ancestor identities.
The row also stores action, predecessor/resulting state, recovery policy/schema,
operator evidence, and creation timestamp. `UNIQUE(session_id,
recovery_ordinal)` fences each per-session ordinal.

The `BEFORE INSERT` trigger requires an open session with no existing
selection, the current recovery counter, a target that resolves through the
immediate-parent chain to that same session, and one exact currently
actionable closed action-matrix entry. Immutable recovery evidence may only be
admitted while the represented recovery action is currently actionable; an
immutable historical fact is never sufficient merely because the target's
aggregate predecessor has not yet changed.

| Action | Target | Predecessor -> result | Effect |
| --- | --- | --- | --- |
| `RECORD_ATTEMPT_AMBIGUITY` | `ATTEMPT` | `LAUNCH_RESERVED` -> `AMBIGUITY_RECORDED` | record resume uncertainty; no fabricated attempt state |
| `RECORD_CLAIM_AMBIGUITY` | `CLAIM` | `COMMITTED` -> `AMBIGUITY_RECORDED` | record uncertainty; claim remains permanent |
| `CLASSIFY_LAUNCH_RESERVATION` | `LAUNCH_RESERVATION` | `COMMITTED` -> `MANUAL_REVIEW` | classify the existing reservation |
| `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` | `LAUNCH_RESERVATION` | `PROCESS_INTENT_COMMITTED` -> `MANUAL_REVIEW` | conservatively classify committed-process-intent uncertainty |
| `CLASSIFY_PRE_RESUME_READY` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | conservatively abandon a process that never received a resume intent |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | `LAUNCH_RESERVATION` | `PROCESS_CREATED` -> `MANUAL_REVIEW` | conservatively classify the committed-intent/no-receipt ambiguity |
| `SELECT_COMMITTED_SUCCESS` | `TERMINAL` | `SUCCEEDED` -> `SUCCESS_SELECTED` | invoke normal owning-session selection |
| `CLOSE_SESSION` | `SESSION` | `OPEN` -> `CLOSED` | close only when all attempts are terminal and none is ambiguous |
| `ACKNOWLEDGE_RESTORE` | `SESSION` | `OPEN` -> `RESTORE_ACKNOWLEDGED` | record restore acknowledgement only |

INSERT-time actionability and later projection freshness are separate checks.
For every action that owns a later aggregate projection, the immutable recovery
row is necessary but is not a reusable authorization token. The projection
trigger independently re-evaluates the mutable normalized predicate at the
exact state or phase update:

| Recovery action | Required current predicate at INSERT | Later projection freshness |
| --- | --- | --- |
| `RECORD_ATTEMPT_AMBIGUITY` | exact committed claim, launch-reserved attempt, `PROCESS_CREATED` reservation, one `RESUME_RECORDED` execution with digest-valid post-resume and cleanup evidence, open session, no terminal/selection | optional attempt and execution ambiguity projections repeat the same active lineage and revocation checks |
| `RECORD_CLAIM_AMBIGUITY` | the targeted committed claim resolves through the same currently actionable attempt/reservation/execution lineage, with no terminal/selection | evidence-only; no aggregate or external authority can be derived from the row |
| `CLASSIFY_LAUNCH_RESERVATION` | active committed claim, launch-reserved attempt, `COMMITTED` reservation, open session, and no execution, terminal, or selection | reservation `MANUAL_REVIEW` repeats the active-lineage predicate |
| `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` | exact active lineage, digest-valid intent, and no failure evidence, execution, terminal, or selection | reservation `MANUAL_REVIEW` repeats those predicates |
| `CLASSIFY_PRE_RESUME_READY` | exact active lineage and one still-`PRE_RESUME_READY` execution with no resume/post-resume/cleanup evidence or terminal/selection | reservation `MANUAL_REVIEW` repeats the exact phase/evidence predicate |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | exact active lineage and one still-`RESUME_INTENT_COMMITTED` execution with no post-resume/cleanup evidence or terminal/selection | reservation `MANUAL_REVIEW` repeats the exact phase/evidence predicate |
| `SELECT_COMMITTED_SUCCESS` | owning confirmed-success terminal, terminal-recorded reservation and attempt, open session, and no prior selection | normal selection and aggregate projection guards recheck ownership and success facts |
| `CLOSE_SESSION` | every current attempt has exact non-ambiguous terminal/selection lineage and the open session has no selection | `OPEN -> CLOSED` repeats the complete current normalized close predicate |
| `ACKNOWLEDGE_RESTORE` | open session with no selection and no prior identical acknowledgement | evidence-only; it changes no aggregate state and grants no capability |

`CLOSE_SESSION` does not race a live external boundary: its prerequisite that
every attempt is terminal means each reservation has already crossed the
terminal writer's OS arbiter and revoked its process-local capabilities. The
close transaction rechecks that durable prerequisite both when the recovery is
inserted and again in the session state trigger. A newly inserted attempt or
changed descendant between those statements makes a historical close row
insufficient and aborts the transition. The normal service keeps recovery
insertion, trigger-owned ordinal increment, close facts, and state projection
inside one `BEGIN IMMEDIATE`; it cannot weaken the predicate, reopen a lineage,
or authorize another provider, process, or resume call.

No generic recovery state ladder exists. Recovery cannot manufacture
`CLAIM_COMMITTED`, `LAUNCH_RESERVED`, `TERMINAL_RECORDED`, or
`SUCCESS_SELECTED` by arbitrary state update, cannot reopen or delete evidence,
and cannot authorize another provider call. A legitimate race may record
uncertainty for distinct existing targets, but it cannot fabricate an attempt
or advance one target twice. The `AFTER INSERT` trigger owns the exact counter
increment, and the reviewed transaction service performs any matrix-authorized
state update in the same `BEGIN IMMEDIATE` transaction.

`CLASSIFY_PRE_RESUME_READY` preserves the conservative operator path before
resume-intent allocation. It requires one digest-valid `PRE_RESUME_READY`
execution with no resume intent, post-resume, or cleanup evidence, records
`MANUAL_REVIEW`, and irrevocably revokes every outstanding resume permit. It
grants no resume or other external authority.

`CLASSIFY_PROCESS_OUTCOME_UNKNOWN` is the sole recovery from
`PROCESS_INTENT_COMMITTED`. It requires digest-valid committed process-intent
evidence, no execution, no definitive process-creation-failure evidence, and
valid operator evidence. A crash after process-intent commit but before
`CreateProcessW` and a crash after `CreateProcessW` but before result/evidence
commit are persistently indistinguishable and therefore share this fail-closed
classification. The transaction appends the immutable recovery row, advances
the recovery counter, and moves the reservation to `MANUAL_REVIEW` atomically
without changing the process-intent facts. It grants no replacement permit,
process call, claim, or provider call and permits only the conservative
`CLOSED`/`MAY_HAVE_OCCURRED` terminal and authorized session-close path.

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
Classification and the resume hook share one OS-backed inter-process lifecycle
arbiter: if classification wins, a delayed hook cannot consume its permit or emit the
external call; if the hook wins, classification may conservatively record the
still-unpersisted outcome after the hook returns. Receipt persistence uses the
same arbitration, so either the receipt commits while the lineage is active or
classification wins and the delayed receipt is rejected without changing the
frozen execution. There is no alternate lineage or permit after classification.
The only subsequent terminal classification is the existing
`CLOSED`/`MAY_HAVE_OCCURRED` entry, after which the normal authorized session
close may run. Recovery remains prohibited after `SUCCESS_SELECTED` or
`CLOSED`.

## 3. Enforcement split

The fixture deliberately enforces only facts that SQLite can evaluate at the
row boundary. The reviewed transaction service and transaction tests enforce
the multi-statement semantic contract.

The execution phase trigger independently requires the same normalized active
parent lineage for both `PRE_RESUME_READY -> RESUME_INTENT_COMMITTED` and
`RESUME_INTENT_COMMITTED -> RESUME_RECORDED`: reservation
`PROCESS_CREATED`, session `OPEN`, no terminal for the reservation, and no
selection for the session. Thus direct SQL cannot bypass a recovery, terminal,
selection, or closure barrier. SQLite can enforce these persisted predicates;
it cannot prove that a real Windows call is not already in flight. Production
adapters must therefore use the reviewed deterministic Windows named mutex.
An in-process substitute or SQLite transaction alone cannot make the final
hook recheck and manual classification mutually exclusive across processes.

### 3.1 Canonical timestamp v1 and causal chronology

Every non-null authority timestamp is canonical timestamp v1: exactly 20 ASCII
characters in `YYYY-MM-DDTHH:MM:SSZ`. The year is four digits from `0001`
through `9999`; the date is valid in the proleptic Gregorian calendar; `T` and
`Z` are literal uppercase characters; and hour, minute, and second are limited
to `00..23`, `00..59`, and `00..59`. UTC is the only representation. Spaces,
lowercase separators, omitted padding, numeric offsets, fractional seconds,
leap seconds, `24:00:00`, and year zero are invalid. A future fractional form
requires a separately reviewed fixed-width schema and policy revision.

The executable schema applies this contract to all 14 timestamp columns,
including every non-null value written to nullable close, process-intent,
outcome, and resume-intent fields. Each column has a deterministic SQLite
`CHECK` combining exact length, a case-sensitive fixed-shape `GLOB`, explicit
year/hour/minute/second ranges, and explicit proleptic-Gregorian arithmetic.
After the digit shape and year range are established, the check casts the
year, month, and day substrings to integers, requires month `1..12` and day at
least one, and caps the day with the exact 31-day, 30-day, and February rule.
February has 29 days precisely when the year is divisible by 400 or is
divisible by 4 but not by 100. No SQLite date/time parser function participates
in the authority decision, so calendar admission is independent of parser
normalization differences between SQLite versions and faithfully covers years
`0001..9999`.

Only after canonical representation and explicit Gregorian validity have been
proven do causal timestamp comparisons use lexical ordering, which is
chronological for this fixed-width UTC form. Every required edge is
nondecreasing (`child >= predecessor`); equality is legal because v1 has
one-second precision. The enforced edge matrix is:

| Child fact | Exact durable predecessor |
| --- | --- |
| migration application and session creation | singleton metadata creation |
| attempt creation | owning session creation |
| claim commit | exact attempt creation |
| reservation commit | exact claim commit |
| process-intent commit | exact reservation commit |
| execution creation | exact reservation process-intent commit |
| `PROCESS_CREATED` first outcome | exact execution creation; the execution already requires the process intent |
| `PROCESS_CREATION_FAILED` first outcome | exact reservation process-intent commit |
| first `MANUAL_REVIEW` outcome from `COMMITTED` or `PROCESS_INTENT_COMMITTED` | exact matching classification recovery, plus the reservation commit or process-intent commit respectively |
| resume-intent commit | exact execution creation |
| `FAILED/NOT_STARTED` terminal | persisted process-creation-failure outcome |
| confirmed success/failure or ordinary post-resume ambiguity terminal | exact execution resume-intent commit |
| ambiguity terminal after attempt/claim ambiguity classification | the matching ambiguity recovery, in addition to the resumed execution predecessor |
| `CLOSED/MAY_HAVE_OCCURRED` terminal | exact matching reservation-classification recovery |
| selection | the exact successful terminal named by `terminal_id` |
| recovery | the action-specific predecessor in the following table |
| `OPEN -> CLOSED` close facts | matching `CLOSE_SESSION` recovery and every terminal already required by that close action |
| `SUCCESS_SELECTED -> CLOSED` close facts | the owning session selection |

Migration application is ordered after metadata creation because provisioning
first inserts the immutable epoch metadata and then appends the migration fact;
it is not an independent administratively prepared timestamp. No edge is added
between independent attempts or other sibling branches.

Recovery timestamps use the latest necessarily causal persisted predecessor:

| Recovery action | Timestamp predecessor |
| --- | --- |
| `RECORD_ATTEMPT_AMBIGUITY` | exact execution resume-intent commit |
| `RECORD_CLAIM_AMBIGUITY` | exact execution resume-intent commit |
| `CLASSIFY_LAUNCH_RESERVATION` | target reservation commit |
| `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` | target reservation process-intent commit |
| `CLASSIFY_PRE_RESUME_READY` | target execution creation |
| `CLASSIFY_RESUME_OUTCOME_UNKNOWN` | target execution resume-intent commit |
| `SELECT_COMMITTED_SUCCESS` | target successful terminal recording |
| `CLOSE_SESSION` | owning session creation and every existing terminal required by the close predicate |
| `ACKNOWLEDGE_RESTORE` | owning session creation |

Every comparison is joined through the exact target and owning session; a
newer fact in another lineage cannot satisfy it. Format and chronology failures
abort the statement, and the surrounding `BEGIN IMMEDIATE` transaction keeps
the child fact, counter or state projection atomic. Immutable predecessor
timestamps cannot be reassigned to manufacture chronology.

Timestamp v1 is an audit representation and chronology contract only. A
timestamp never grants or revokes a capability, decides whether an external
API occurred, replaces current-state predicates or the OS inter-process
arbiter, establishes retry eligibility or freshness, or supplies trusted
exchange time. It is absent from every UUID5 identity tuple. Unattended
scheduling therefore remains `NO-GO`; valid chronology does not make local
wall-clock input trusted authority.

### 3.2 Persisted evidence-pair inventory

Every persisted column whose name ends in `_json` has one declared SHA-256
digest and an authoritative SQLite validation boundary. Digest length alone is
never content integrity. The complete executable inventory is:

| Table | JSON/BLOB and digest | Ownership class | Authoritative validation |
| --- | --- | --- | --- |
| `authority_metadata` | `metadata_json` / `metadata_digest` | owned at insert | metadata `BEFORE INSERT` trigger |
| `schema_migrations` | `migration_json` / `migration_digest` | owned at insert | migration `BEFORE INSERT` trigger |
| `sessions` | `request_json` / `request_digest` | owned at insert | session `BEFORE INSERT` trigger |
| `attempts` | `request_json` / `request_digest` | copied from session | exact parent bytes/digest plus hash at attempt insert |
| `attempts` | allocation evidence and attempt evidence JSON/digest pairs | owned at insert | attempt `BEFORE INSERT` trigger |
| `provider_call_claims` | `request_json` / `request_digest` | copied from attempt | exact parent bytes/digest plus hash at claim insert |
| `provider_call_claims` | claim evidence JSON/digest | owned at insert | claim `BEFORE INSERT` trigger |
| `launch_reservations` | reservation evidence JSON/digest | owned at insert | reservation `BEFORE INSERT` trigger |
| `launch_reservations` | process-intent and process-creation-failure JSON/digest pairs | appended on update | controlled null-to-value transition triggers |
| `launch_executions` | process-creation, Job Object, and resume-authorization JSON/digest pairs | owned at insert | execution `BEFORE INSERT` trigger |
| `launch_executions` | resume-intent, post-resume, and cleanup JSON/digest pairs | appended on update | controlled null-to-value transition triggers |
| `terminals` | terminal evidence and sanitized-diagnostics JSON/digest pairs | owned at insert | terminal `BEFORE INSERT` trigger, before the terminal matrix |
| `session_selections` | selection evidence JSON/digest | owned at insert | selection `BEFORE INSERT` trigger |
| `manual_recoveries` | operator evidence JSON/digest | owned at insert | recovery `BEFORE INSERT` trigger |

For every owned or appended pair, SQLite requires
`sha256(blob) IS digest` at the write that first persists the bytes. Copied
request pairs additionally require exact immediate-parent byte and digest
equality. Parent evidence is immutable, so later parent drift is rejected.
Append triggers require an exact null-to-paired-value transition and reject the
whole update atomically on a wrong digest. Terminal evidence and sanitized
diagnostics are validated before any `SUCCEEDED`, `FAILED`, `AMBIGUOUS`, or
`CLOSED` matrix entry can be accepted; malformed terminal evidence therefore
cannot become a selected success.

Several digest columns intentionally have different semantics and are not the
hash of an adjacent JSON column: `bootstrap_digest` authenticates the signed
bootstrap bytes; `database_identity_digest` binds the provisioned database;
`application_release_digest` binds release material; reservation and terminal
`request_digest` values copy the canonical request hash without another local
request blob; terminal `snapshot_digest` hashes verified snapshot content; and
selection `snapshot_digest` copies that terminal snapshot hash. These columns
retain their existing lineage or external-artifact rules and are not falsely
treated as JSON pairs.

This content-integrity layer is separate from lineage, which proves copied
facts match their immediate parent; provenance, which is modeled by private
typed issuers and process-local one-shot permits; exclusion, which is provided
by the OS-backed inter-process arbiter; and external effects, which SQLite
cannot prove occurred at a provider or Windows API boundary.

### 3.3 Durable fact / aggregate projection invariant

Aggregate state and phase columns are indexes over, and verified projections
of, normalized durable facts. A state value alone is never evidence that the
represented operation occurred. Where SQLite can evaluate both sides, child
admission requires the exact immediate-parent predecessor and every aggregate
advance requires the corresponding child fact or paired immutable evidence.
No direct SQL writer may manufacture operational progress merely by changing a
state or phase column.

Process intent, process-creation failure, resume intent, and resume result are
paired with their aggregate transition in one guarded row update. For separate
rows, the transaction inserts the durable child first and advances the
aggregate second. External API occurrence remains outside SQLite and continues
to require committed intents, exact typed results, OS-backed inter-process
arbitration, and conservative recovery.

| Table / state or phase | Predecessor | Durable fact first | Projection second | Immediate-parent lineage and SQL guard | Recovery, selection, or closure semantics |
| --- | --- | --- | --- | --- | --- |
| `sessions.OPEN` | none | canonical session row with both counters zero and no close facts | row begins `OPEN` | metadata policy and request-digest insert trigger | only state eligible for attempts, selection, or recovery |
| `sessions.SUCCESS_SELECTED` | `OPEN` | owning `session_selection` for a successful terminal | session becomes `SUCCESS_SELECTED` | selection -> terminal -> reservation -> claim -> attempt -> same session; session state trigger requires the selection | absorbing for selection and recovery |
| `sessions.CLOSED` | `OPEN` or `SUCCESS_SELECTED` | `CLOSE_SESSION` recovery for `OPEN`, or the existing selection for `SUCCESS_SELECTED`; immutable close facts | session becomes `CLOSED` | the exact transition rechecks every current attempt's normalized terminal/selection lineage and absence of ambiguity; state and close-fact triggers require the authorizing fact | no launch, selection, or recovery authority remains |
| `attempts.ALLOCATED` | open session/current ordinal | immutable attempt and allocation evidence | row begins `ALLOCATED` | attempt -> session -> metadata insert trigger; session counter advances after insert | no claim fact yet |
| `attempts.CLAIM_COMMITTED` | `ALLOCATED` | exact immutable `provider_call_claim` | attempt becomes `CLAIM_COMMITTED` | claim's attempt, request, provider, operation, budget, and policy must match | claim remains permanent |
| `attempts.LAUNCH_RESERVED` | `CLAIM_COMMITTED` | exact reservation through that claim | attempt becomes `LAUNCH_RESERVED` | reservation -> claim -> exact attempt in an open session | one reservation fence only |
| `attempts.LAUNCH_MAY_HAVE_OCCURRED` | `LAUNCH_RESERVED` | matching `RECORD_ATTEMPT_AMBIGUITY` recovery | optional ambiguity projection | exact active claim/reservation/resumed-execution lineage in an open session, with no terminal or selection, is rechecked | recovery records uncertainty; it grants no retry |
| `attempts.TERMINAL_RECORDED` | `LAUNCH_RESERVED` or `LAUNCH_MAY_HAVE_OCCURRED` | terminal through the exact claim/reservation | attempt becomes `TERMINAL_RECORDED` | terminal -> reservation -> claim -> exact attempt | terminal is immutable |
| `attempts.SUCCESS_SELECTED` | `TERMINAL_RECORDED` | owning selection for that attempt's successful terminal | attempt becomes `SUCCESS_SELECTED` | selection and terminal must resolve to the same attempt and session | absorbing until optional close projection |
| `attempts.CLOSED` | terminal or selected attempt | durable terminal/selection plus closed owning session | attempt optionally becomes `CLOSED` | normalized terminal lineage and session `CLOSED` are required | no operational authority |
| `provider_call_claims.COMMITTED` | attempt `ALLOCATED` | immutable claim row | attempt may become `CLAIM_COMMITTED` | normalized attempt/session admission policy and exact copied request/policy facts | evidence-only claim ambiguity does not mutate the permanent claim |
| `launch_reservations.COMMITTED` | claim `COMMITTED`, attempt `CLAIM_COMMITTED` | immutable reservation row | attempt may become `LAUNCH_RESERVED` | reservation -> exact claim -> attempt -> open session insert guard | provider-construction handoff only |
| reservation `PROCESS_INTENT_COMMITTED` / `PROCESS_CREATION_FAILED` | `COMMITTED` / `PROCESS_INTENT_COMMITTED` | canonical process intent / exact `NOT_CREATED` failure pair | paired reservation transition in the same guarded update | process intent also rechecks the committed claim, launch-reserved attempt, open session, copied request/policy lineage, and absence of execution, terminal, or selection; append-only evidence/digest guards apply and failure forbids an execution | intent does not prove the external call; failure is definitive no-process evidence |
| reservation `PROCESS_CREATED` | `PROCESS_INTENT_COMMITTED` | exact execution row with creation, Job Object, and resume-authorization evidence | reservation becomes `PROCESS_CREATED` | execution -> exact reservation; reservation projection requires that execution | typed external result remains required by the service |
| reservation `MANUAL_REVIEW` | documented recoverable reservation predecessor | matching immutable recovery row | reservation becomes `MANUAL_REVIEW` | recovery action, predecessor, target, exact current phase/evidence, active same-session lineage, and absence of newer terminal/selection facts are rechecked | recovery-owned and irreversible |
| reservation `TERMINAL_RECORDED` | eligible created, failed, or manual-review state | exact immutable terminal | reservation becomes `TERMINAL_RECORDED` | terminal references that reservation | terminal revokes delayed authority |
| execution `PRE_RESUME_READY` | reservation `PROCESS_INTENT_COMMITTED` | immutable execution row | reservation may become `PROCESS_CREATED` | normalized reservation -> claim -> attempt -> open session insert guard | no resume intent yet |
| execution `RESUME_INTENT_COMMITTED` / `RESUME_RECORDED` | `PRE_RESUME_READY` / `RESUME_INTENT_COMMITTED` | canonical resume intent / exact post-resume and cleanup pairs | paired phase transition in the same guarded update | active normalized lineage, no terminal or selection | persisted intent/result does not let SQLite prove the Windows call |
| execution `POST_RESUME_AMBIGUOUS` | `RESUME_RECORDED` | matching attempt-ambiguity recovery | optional ambiguity phase projection | exact active reservation/claim/attempt/open-session lineage and absence of terminal or selection are rechecked | conservative, no retry authority |
| execution `TERMINAL_RECORDED` / `CLOSED` | resumed or ambiguous / terminal | exact terminal / terminal plus closed session | execution phase advances | terminal -> exact reservation; closure also resolves to session `CLOSED` | absorbing projections |
| `terminals` | exact eligible reservation/execution predecessor | immutable terminal row satisfying the state/disposition/snapshot matrix | execution, reservation, and attempt become `TERMINAL_RECORDED` | terminal insert resolves reservation -> claim -> attempt -> open session | ambiguity and manual-review close remain conservative |
| `session_selections` | successful terminal, terminal-recorded attempt, open session | immutable owning selection row | attempt and session become `SUCCESS_SELECTED` | complete terminal -> reservation -> claim -> attempt -> session ownership guard | normal and recovery-driven selection use the same fact |
| `manual_recoveries` | exact action-matrix predecessor in an open session | immutable recovery row at the current ordinal | counter increments, then any recovery-owned projection advances | typed target resolves through immediate parents to the same session | evidence-only actions do not themselves mutate aggregate state; any optional ambiguity projection must cite that row; classification and close actions are irreversible |

No historical state-producing recovery row is sufficient by itself: each
projection guard repeats every mutable eligibility fact it can observe. A
terminal inserted after attempt-ambiguity recovery, an execution or resume
fact persisted after classification recovery, or a new attempt inserted after
close recovery invalidates the later projection rather than consuming an
alternate action.

`CLOSE_SESSION` therefore cannot trust a terminal-looking attempt state. Every
`TERMINAL_RECORDED`, `SUCCESS_SELECTED`, or `CLOSED` attempt admitted by the
close matrix must resolve through its exact claim and reservation to the
required terminal, and a selected attempt must additionally resolve to the
owning session selection. Missing or contradictory lineage aborts the recovery
insert, counter increment, close facts, and session transition atomically in
the normal transaction. An allocated but unclaimed attempt is an inert audit
row, not external authority; selection or closure makes its future claim
admission impossible.

### 3.4 Final capability matrix

Canonical bytes and SHA-256 digests establish content integrity only. The
matrix deliberately separates durable SQLite state, process-local typed-object
provenance, OS-backed inter-process arbitration, and the external effect or
result. Private typed issuers plus registries bind each one-shot permit to the
exact issued object and immutable original lineage only in its issuing process.
Registry-side lineage, never caller-visible attributes, selects the arbiter,
database facts, and event identity. A copied, reconstructed, reflectively
mutated, cross-process, wrong-issuer, or wrong-permit object has no authority
even when its public bytes are exact. Persisted parent state and the OS arbiter
remain independently necessary.

| Boundary | Required persisted parent | Capability/evidence | Issuer/provenance | Consumption point | Lifecycle arbiter | Database transaction | Revoking facts | Crash result / recovery | Direct-SQL enforcement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Reservation/provider-permit issuance | `COMMITTED` claim in an `OPEN` session | Unique reservation insert produces frozen `FakeProviderConstructionPermit` | Immutable registry record owns exact object and original reservation ID | Permit remains live until provider construction | Persisted writers serialize through `BEGIN IMMEDIATE` | Yes, `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, process intent, terminal, selection, `CLOSED` | Before commit: no reservation/permit; after commit with lost permit: `CLASSIFY_LAUNCH_RESERVATION` | Unique `claim_id`, reservation lineage trigger; SQL cannot issue the permit |
| Provider construction | `COMMITTED` reservation, exact normalized active lineage, no process intent/execution/terminal/selection | Exact `FakeProviderConstructionPermit` produces `FakeConstructedProvider` | Registry-bound reservation selects arbiter, SQL lineage, event, and result; visible fields are checked only | Reservation permit immediately before construction; constructed provider after process-intent commit | Required; held through constructed-provider production | No transaction across construction | `MANUAL_REVIEW`, process intent, terminal, selection, `CLOSED` | Failure or loss leaves `COMMITTED`; never reconstruct/repeat, use `CLASSIFY_LAUNCH_RESERVATION` | SQLite proves reservation ownership, not provider-object construction |
| Process-intent issuance | `COMMITTED` reservation and exact normalized claim/session lineage | Exact `FakeConstructedProvider` produces transaction-issued `FakeProcessIntent` | Private issuers and exact object/permit registries | Constructed provider after commit; process permit at dispatch | Required against reservation classification | Yes, `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Rollback while active preserves exact provider capability; after commit no process-permit reconstruction, use `CLASSIFY_PROCESS_OUTCOME_UNKNOWN` | Process-intent append/state triggers; provider provenance remains service-only |
| Process dispatch | `PROCESS_INTENT_COMMITTED`, committed claim, launch-reserved attempt, `OPEN`, no terminal/selection | Exact `FakeProcessIntent` | Private issuer and exact registered one-shot permit | Immediately before `CreateProcessW` | Required; held through typed result production | No transaction across call | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | No result is indistinguishable from unpersisted result; classify unknown | SQL cannot perform or prove the API call |
| Process-success persistence | Same active process lineage; no execution | Exact `FakeProcessCreationReceipt` | Private result issuer and exact registered result permit | After execution/reservation commit | Required | Yes, `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Rollback while active keeps receipt retryable; otherwise classify unknown | Execution parent trigger and reservation state trigger; provenance remains service-only |
| Process-failure persistence | Same active process lineage; no execution/failure | Exact `FakeProcessCreationFailure` with `NOT_CREATED` | Private result issuer and exact registered result permit | After failure/state commit | Required | Yes, `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Rollback while active keeps failure retryable; otherwise classify unknown | Failure evidence/state triggers; provenance remains service-only |
| Resume-intent issuance | `PRE_RESUME_READY`, `PROCESS_CREATED`, `OPEN`, no terminal/selection | Transaction-issued `FakeResumeIntent` | Private intent issuer; exact object/permit registry | Permit remains live until resume dispatch | Required against reservation classification | Yes, `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Before commit use pre-resume recovery; after commit classify unknown | Execution phase/evidence trigger with normalized parent join |
| `ResumeThread` dispatch | `RESUME_INTENT_COMMITTED` with exact active lineage | Exact `FakeResumeIntent` | Private issuer and exact registered one-shot permit | Immediately before `ResumeThread` | Required; held through receipt production | No transaction across call | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Missing persisted receipt is unknown; classify unknown | SQL cannot perform or prove the API call |
| Resume-success persistence | Same active resume lineage and current intent | Exact `FakeResumeReceipt` | Private resume-result issuer and exact registered result permit | After receipt/cleanup commit | Required | Yes, `BEGIN IMMEDIATE` | `MANUAL_REVIEW`, terminal, selection, `CLOSED` | Rollback while active keeps receipt retryable; otherwise classify unknown | Execution phase/evidence trigger; provenance remains service-only |
| Terminal recording | State-specific reservation matrix | Canonical terminal evidence and optional verified snapshot | Reviewed transaction service and terminal policy | Unique terminal insert | Required for that reservation; terminal is an immediate revocation boundary | Yes, `BEGIN IMMEDIATE` | Existing terminal, selection, `CLOSED`; `MANUAL_REVIEW` permits only conservative close | Rollback leaves no terminal; retry only under unchanged state | Terminal matrix, uniqueness, and normalized lineage triggers |
| Selection | Confirmed successful terminal in owning `OPEN` session | Terminal identity and normal or recovery-authorized selection request | Reviewed transaction service and selection policy | Unique session selection insert | No external-dispatch arbiter | Yes, `BEGIN IMMEDIATE` | Existing selection, `SUCCESS_SELECTED`, `CLOSED` | Rollback leaves no selection; retry under unchanged success | Selection ownership/state trigger and uniqueness |
| Recovery classification | `OPEN` session and exact action-matrix predecessor | Typed target, operator evidence, policy, current recovery ordinal | Reviewed recovery service; immutable operator evidence | Recovery row and ordinal consumed atomically | Required for reservation actions that arbitrate external work | Yes, `BEGIN IMMEDIATE` | `SUCCESS_SELECTED`, `CLOSED`, changed predecessor, prior classification | Rollback consumes no ordinal; commit is irreversible and authorizes no replacement operation | Recovery target/action trigger; service pairs row, counter, and state transition |

The signed bootstrap and immutable metadata own the permitted public Alpaca
descriptor and select authority/claim policy versions. The reviewed service
first rejects metadata policies this release does not implement, snapshots and
validates caller-owned input, then performs descriptor and canonical-request
semantic reconciliation before deriving the service-owned UUID5 identity.
Independently, `sessions_before_insert` uses native JSON1 to admit only the
exact canonical persisted `capture_request/v2`, enforce its existing field,
type, fixed-value, Symbol-text, bound, date, and digest contract, and bind its
target/provider/operation semantics to the session and metadata columns.
Immediate descendants can only copy the session-owned bytes/digest through
their persisted parent lineage. SQLite does not authenticate callers, derive
UUID5 identities, invoke external provider behavior, or prove Windows effects.

| SQLite schema, constraints, and triggers | Reviewed transaction service/tests |
| --- | --- |
| Immediate-parent foreign keys and `foreign_key_check` integrity | Workflow ordering across multiple statements and tables |
| Normalized metadata/session/attempt/claim/reservation/execution policy-binding checks | Release-support validation before session canonicalization or identity derivation |
| Canonical session-request admission, redundant target/descriptor binding, append-only immutable evidence, canonical resume-intent/receipt bytes, and prohibited deletes | Caller-input snapshot, public `Symbol` validation, canonical construction, UUID5 derivation, and release-policy reconciliation |
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

Any caller-supplied attempt ordinal override is validated before UUID5 or
evidence derivation and before the transaction begins. Its exact Python type
must be `int` (not `bool`, float, string, coercible numeric, or an `int`
subclass) and its value must be non-negative. The counter read from SQLite is
validated through the same canonical domain before use.

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

Caller-supplied recovery ordinal overrides use the same exact non-negative
Python `int` contract before arbiter selection, UUID5 material, evidence text,
or transaction work. Rejection leaves the row set and both counters unchanged;
SQLite remains authoritative for whether a valid canonical ordinal equals the
currently allocated counter.

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
contents are `LF(item_count)` followed by each item frame in the order captured
by the immutable validated request snapshot. No identity uses a clock, UUID4,
Python hash, object identity, locale,
filesystem path, secret, row order, or serialized artifact bytes.

Persisted schema/version values used by deterministic identities must equal the
version encoded in the canonical UUID5 tuple. This release supports exactly
schema `1` for `sessions`, `attempts`, `provider_call_claims`,
`launch_reservations`, `launch_executions`, `terminals`,
`session_selections`, and `manual_recoveries`; each column has an authoritative
`CHECK(schema = 1)`. Values 0, 2, and all other alternatives fail at direct SQL
insertion. `authority_metadata.bootstrap_schema` and
`schema_migrations.schema_version` retain their distinct bootstrap and
migration versioning semantics and are not part of this row-schema gate.

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

Identity helpers have no hidden policy defaults. Each policy-bearing tuple
receives the exact value that will be persisted in that row, sourced from its
already-persisted parent where the policy is copied. Terminal, selection, and
recovery helpers likewise receive their row policy explicitly. Their
normalized parent references preserve the upstream authority/claim lineage
without copying ancestor IDs or independently choosing those policy versions.
Changing an explicit policy input changes the identity material; an
unsupported metadata policy is rejected before any identity is constructed.

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
`BEGIN IMMEDIATE`. The service verifies the fixed bootstrap/epoch/schema, then
copies and validates the caller request into one immutable
`ValidatedCaptureRequest` before opening the session-creation transaction. The
transaction reconciles metadata and snapshot descriptor semantics before
canonicalization, identity derivation, or session insertion. Every later read
for canonical bytes, digest, identity material, target date, and inserted
session facts comes from that same snapshot. Uncommitted work rolls back;
committed evidence is never repaired by deleting rows.

The required order is:

```text
fixed bootstrap/CNG/ACL/path verification
  -> exact caller-request copy, Symbol validation, and immutable snapshot
  -> session BEGIN IMMEDIATE
  -> read singleton metadata and reconcile the exact public Alpaca descriptor
  -> snapshot serialization, digest, session identity, insert, and COMMIT
  -> attempt ordinal transaction
  -> permanent claim transaction and COMMIT
  -> launch reservation transaction and COMMIT
  -> one-shot credential/provider/network construction using the reservation-issued permit
  -> process-intent transaction and PROCESS_INTENT_COMMITTED COMMIT
  -> external CreateProcessW(CREATE_SUSPENDED) through the reviewed adapter using the one-shot permit
  -> exact typed process/Job Object result returned to the transaction service
  -> successful process/Job Object/PRE_RESUME_READY evidence transaction and COMMIT
  -> resume intent transaction and RESUME_INTENT_COMMITTED COMMIT
  -> external ResumeThread through the reviewed adapter using the one-shot permit
  -> exact canonical successful resume receipt returned to the transaction service
  -> paired post-resume and cleanup evidence transaction and COMMIT
  -> terminal matrix validation and immutable terminal transaction
  -> execution/reservation/attempt terminal-recorded transitions in that transaction
  -> explicit successful session selection
```

The claim and unique reservation commits both precede all
credential/provider/network construction. The claim insertion is the
session-wide admission point: the authoritative trigger rejects every prior
outcome except the exact digest-valid
process-creation-failure `FAILED`/`NOT_STARTED` lineage with no execution. The
reservation insert is the durable construction handoff and alone issues its
opaque permit. The permanent claim cannot reconstruct it. The helper does not
run an ad hoc unresolved-execution query.

The reservation permit is consumed immediately before one provider construction
under the lifecycle arbiter. Its exact typed result is consumed only after the
separate `BEGIN IMMEDIATE` process-intent transaction commits. The reservation,
provider construction, and process-intent commits all precede process creation.
Only the process-intent winner receives the one-shot permit accepted by the
reviewed adapter. Process dispatch and manual
classification are mutually exclusive under the OS-backed inter-process
lifecycle arbiter: recovery-first emits no call, while dispatch-first emits
exactly one call and produces exactly one privately issued result before releasing the
arbiter. The exact registered successful result then authorizes the
`PRE_RESUME_READY` execution row containing process, Job Object, and
resume-authorization evidence. Result persistence uses the same arbiter and
consumes the result only after commit. A separate `BEGIN IMMEDIATE`
transaction then appends the canonical resume intent and
commits `RESUME_INTENT_COMMITTED`; only that winner receives the one-shot
permit accepted by the reviewed adapter. The adapter observes that committed
state and rechecks the normalized active lineage immediately before the call,
performs the modeled external call once, and returns the exact canonical
success receipt bound to the execution and intent digest. Only then may the
transaction service, after another full active-lineage recheck, persist the
receipt as post-resume evidence, persist cleanup evidence, verify both digests,
and advance the execution to `RESUME_RECORDED`. SQLite enforces the durable
one-reservation and one-intent fences, exact persisted bytes, active-parent
phase guards, and persisted barriers; it cannot prove that an external Windows
API call occurred or arbitrate a call already outside SQLite.

A crash after reservation commit but before provider construction, a provider
construction failure, or loss of its successful in-memory result before
process-intent commit leaves `COMMITTED`. The service must never reconstruct or
repeat construction and uses only `CLASSIFY_LAUNCH_RESERVATION`. A transient
process-intent rollback in the same live service may retry once with the exact
still-registered constructed-provider capability. A crash after process-intent
commit but before `CreateProcessW` and a crash after
`CreateProcessW` but before its typed result is committed both leave
`PROCESS_INTENT_COMMITTED` with no execution or definitive failure evidence.
The service must not recreate a permit or retry the call; it uses only
`CLASSIFY_PROCESS_OUTCOME_UNKNOWN` and the conservative close path. A crash
before resume-intent commit leaves `PRE_RESUME_READY`, where the separate
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
effect. Classification is an irreversible revocation barrier: a previously
issued permit, a delayed hook invocation, and a delayed successful receipt are
all insufficient after it commits. The hook and recovery transaction must be
serialized per reservation; receipt persistence participates in the same
arbitration. The process-result boundary applies the analogous rule: a delayed
successful process receipt cannot create an execution after
`CLASSIFY_PROCESS_OUTCOME_UNKNOWN`.

The whole-boundary audit treats every arrow from claim commit through
selection as an authority handoff: claim commit -> reservation commit ->
provider construction -> process-intent commit -> `CreateProcessW` -> exact typed
process result -> `PRE_RESUME_READY` commit -> resume-intent commit ->
`ResumeThread` -> exact receipt/evidence commit -> terminal -> selection.
Positive, rejection, two-connection concurrency, and crash cases cover each
handoff. One reservation plus one committed process intent and its opaque
winner permit fence `CreateProcessW`; one committed resume intent and its
opaque winner permit fence `ResumeThread`. Only exact intent-bound typed
results advance either boundary. Every uncertainty path remains
claim-blocking. The canonical request bytes propagated through the
lineage, target date, and UUID5 identity material all come from one frozen
validated snapshot; caller mutation and alternate representations never reach
or split those boundaries.

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
- native JSON1 canonical session-request admission, exact target/metadata
  binding, and session-to-immediate-parent propagation/mismatch rejection;
- the complete terminal state/disposition matrix and append-only paired launch
  evidence rules;
- the authoritative session-wide claim-admission matrix through both helper
  and direct insertion, including the sole retry-safe prior lineage;
- reservation-only `COMMITTED` insertion, append-only canonical process intent,
  first-outcome timestamp preservation, and write-once session close facts;
- attempt and recovery ordinal races, stale/future ordinals, direct-counter
  rejection, rollback atomicity, and independent session ordinals;
- the closed recovery action matrix, including distinct-target races and
  table-driven invalid lifecycle transitions;
- a process-intent concurrency winner, one-shot typed process result contracts,
  a process-creation failure terminal without an execution row, and
  conservative unknown-process and unknown-resume recovery/close paths; and
- fake side-effect hooks proving claim, reservation, process-intent,
  `CreateProcessW`, pre-resume, resume-intent, `ResumeThread`, post-resume, and
  terminal ordering; exact receipt binding; and no new claim after either
  unresolved external-call outcome.

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
