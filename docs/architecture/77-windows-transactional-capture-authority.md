# Windows transactional capture authority

## Scope and decision

This architecture replaces the executable file-based provider-call authority
with a deployment-pinned, signed bootstrap and a single SQLite authority
database. It is a design milestone only. It does not implement runtime code,
database code, provisioning, credential access, provider access, migrations, or
tests. Paper operation and real-money trading remain outside this boundary.

The authority is for one manually guarded, long-only market-data capture at a
time. A committed provider-call claim is permanent. The database, not a
directory scan, a history pointer, a claim file, or a launcher-supplied path,
decides whether a provider call may be attempted.

The initial deployment is fixed to:

```text
F:\AITradingBot\Authority\
  authority.bootstrap.json
  authority.bootstrap.sig
  authority.sqlite3
  authority.sqlite3-journal
  capture-output\
  backup\
```

The bootstrap records the exact database and capture-output paths. The
bootstrap directory is not configurable by a runner, launcher, child,
environment, allocation, request, or database row.

## 1. Threat model and trust boundary

### Covered threats

The design explicitly covers:

- duplicate or concurrent runner and child processes, including two processes
  accidentally or cooperatively attempting the same allocation under the
  trusted Trading token;
- crashes before claim commitment, after claim commitment, before resume,
  after resume, during result recording, and during success selection;
- caller-controlled configuration, paths, files, current directory, and
  environment variables;
- other non-administrative Windows accounts attempting to read, replace, or
  influence authority material;
- copied or cloned capture roots, including a root presented through a
  different path or volume;
- rollback cases that are visible through independently retained signed
  bootstrap state, including an older bootstrap generation or an old epoch;
- filesystem links, junctions, mount points, and other reparse points in any
  authority or capture path component;
- process and credential isolation, including secret-free parent state,
  current-process SID verification, child-only Credential Manager reads,
  constrained child environment, and native cleanup; and
- malicious provider responses and diagnostics that contain secrets, arbitrary
  text, or misleading status. Only bounded, typed, sanitized evidence is
  admitted to the database or output.

The threat model assumes that provider responses, child output, launcher
configuration, and all non-authoritative files are hostile input. It also
assumes that a process can disappear at any instruction boundary after a
provider claim is committed.

### Trust boundary

The trusted path is the approved signed application release, its pinned
bootstrap-verification key, the administrator-provisioned bootstrap and ACLs,
the exact local NTFS paths, the verified authority epoch, SQLite's durable
transaction result, and the Windows native process/credential primitives used
by the child boundary. The dedicated `Trading` account and approved processes
running under its token are trusted to honor this contract. SQLite constraints
serialize accidental duplicate or cooperating approved processes; they do not
authenticate an executable or protect against code that already controls the
trusted token. A provider response is never trusted as authority; it becomes
evidence only after strict validation and sanitization.

The following are explicitly outside the trust boundary:

- compromise of the dedicated `Trading` account;
- arbitrary or unapproved code executing under the Trading token;
- direct malicious database modification by the Trading account;
- a compromised local Administrator or SYSTEM account;
- replacement of the approved signed application release;
- compromise of the offline bootstrap signing key; and
- kernel compromise.

Those conditions invalidate the deployment assumption and require
administrator-led recovery or re-provisioning. The design does not claim to
make a compromised privileged host or compromised Trading token safe.
Protecting against hostile same-account code would require a separately
designed broker service that owns the authority and provider boundary; that
broker is not part of this architecture.

### Rollback boundary and replacement cases

The authority distinguishes three classes of replacement and rollback:

1. **Detectable with independently retained signed/bootstrap state.** An
   older-generation database, an epoch that no longer matches the signed
   bootstrap, altered bootstrap or signature material, a copied root, and a
   path alias can be rejected when the approved release has independently
   retained signed/bootstrap facts, fixed-path/final-handle checks, or both.
   The database's own metadata is reconciled with those independently retained
   facts before executable use.
2. **Approved restore.** Every administrator-approved restore is
   historical-only. It requires a rotated signed bootstrap generation, a new
   `authority_epoch_id`, a newly provisioned empty executable database, and no
   import or executable reuse of old allocations or claims. The restored
   database may be inspected and preserved as evidence, but it is never the
   executable authority for the new epoch.
3. **Outside the trust boundary.** A database cannot prove its own freshness
   after the database and persistent journal have been completely replaced by
   an internally consistent same-generation pair. Replacement by
   Administrator/SYSTEM, malicious direct database modification by the trusted
   `Trading` account, or arbitrary code controlling that account is outside
   this threat model. This milestone adds no external service, hardware
   monotonic anchor, or other independent freshness authority to detect those
   cases.

An internally consistent same-generation replacement is therefore not a
validation failure for this design; it is an explicit trust-boundary
limitation. `database_identity_digest` is a database-local consistency field,
not an externally retained rollback anchor and not proof of freshness after a
complete replacement.

## 2. Deployment-pinned signed bootstrap

### Fixed location and fields

The only accepted bootstrap location is:

```text
F:\AITradingBot\Authority\authority.bootstrap.json
F:\AITradingBot\Authority\authority.bootstrap.sig
```

The release contains this location as a constant. It is not read from runner
configuration, launcher configuration, child CLI arguments, environment,
allocation data, request data, or SQLite content. The database path and output
root are likewise fixed by the signed bootstrap, not selected by a caller.

The bootstrap's canonical JSON object contains exactly these semantic fields:

| Field | Meaning |
| --- | --- |
| `bootstrap_schema` | Bootstrap schema number, initially `1`. |
| `bootstrap_generation` | Positive administrator-controlled generation; it increases on controlled rotation. |
| `signing_key_id` | Identifier for the public key pinned in the approved release. |
| `machine_authority_id` | Stable signed administrator-provisioned UUID fact for this machine authority; not runtime-derived UUID5 material. |
| `authority_epoch_id` | Signed administrator-provisioned UUID fact for this executable authority epoch; not runtime-derived UUID5 material. |
| `approved_account_sid` | Exact Windows SID allowed to consume the authority and child boundary. |
| `authority_database_path` | Exact absolute path `F:\AITradingBot\Authority\authority.sqlite3`. |
| `capture_output_root` | Exact absolute path `F:\AITradingBot\Authority\capture-output\`. |
| `provider_id` | Fixed provider descriptor, initially `ALPACA_MARKET_DATA`. |
| `permitted_provider_operation` | Exact approved operation, initially historical daily-bars capture. |
| `authority_policy_version` | Version of state, evidence, and authority rules. |
| `claim_policy_version` | Version of the one-per-allocation claim rules. |
| `created_at_utc` | Provisioning-supplied UTC fact; never generated as an identity input. |
| `predecessor_bootstrap_digest` | Optional SHA-256 digest of the predecessor bootstrap for controlled rotation. |

The canonical serializer rejects duplicate or unknown members, floats,
noncanonical timestamps, invalid SIDs, path aliases, non-absolute paths, and
noncanonical JSON bytes. Identity material is explicit and length-framed; it
contains the schema, generation, key ID, machine authority, epoch, account
SID, provider operation, and policy versions, but not paths, clocks supplied at
runtime, serialized artifact bytes, or secrets.

The detached signature covers the exact canonical UTF-8 bootstrap bytes. The
signature file has a fixed binary envelope containing a signature-envelope
schema, `signing_key_id`, signed-bootstrap SHA-256, and the signature. The
envelope is not authority by itself: the verifier checks that its key ID and
digest match the canonical bootstrap and then verifies the signature. The
signature and bootstrap are never rewritten by a trading process.

### Selected signing design

The selected primitive is ECDSA over NIST P-256 with SHA-256, verified through
Windows CNG (`BCryptVerifySignature`) using a fixed signature encoding and
explicit test vectors. Provisioning may sign offline with a CNG-compatible
tool, but the private signing key is never present in the deployment tree.

This is preferred here over a bundled cryptographic library because the
Windows verifier is supplied by the operating system, avoids a runtime
OpenSSL/PyPI dependency in the authority path, and can be constrained to the
approved algorithm and public key. ECDSA signatures are not used as
deterministic domain identities; only the signed canonical bytes and public-key
verification matter. The exact CNG signature encoding, hash input, and key
serialization are part of the release contract and must have golden vectors.
The trade-off is a Windows-native verifier and a requirement to validate CNG
behavior on every supported Windows release. A release that cannot perform
the pinned CNG verification fails closed.

### Verification order

Before any database mutation, process creation, SID access, Credential Manager
access, provider construction, or transport, the approved release must:

1. open only the fixed bootstrap and signature paths;
2. verify every path component and final handle path is the exact expected
   local path, with no reparse point, junction, mount point, or link;
3. verify owner and DACL semantics;
4. parse strict canonical bytes and verify the detached signature, key ID,
   bootstrap digest, field policy, and generation/epoch constraints; and
5. bind the verified values to the current release, exact database path,
   exact capture root, and approved account SID.

Failure at any step stops before SQLite is opened for mutation and before any
process or secret boundary is entered.

## 3. Windows provisioning and ACL contract

### Administrator-only provisioning

Provisioning is an explicit administrator workflow. It creates the fixed
directory, writes the bootstrap and detached signature, creates the empty
authority database and persistent rollback journal in advance, applies ACLs,
verifies final paths, and records the provisioning evidence. It may rotate an
epoch only as a reviewed operation. Unattended operation is not approved by
this contract.

The dedicated `Trading` account is a standard non-administrative account. It
does not own the authority tree, cannot grant itself rights, and cannot access
the offline signing key or backup directory.

### Owner and DACL semantics

Inheritance is disabled on the authority directory and on each authority
file. Expected owner and DACL semantics are:

| Object | Owner | Required allows | Required denies / prohibitions |
| --- | --- | --- | --- |
| `F:\AITradingBot\Authority\` | `BUILTIN\Administrators` (or `SYSTEM` when the reviewed provisioning policy selects it) | SYSTEM full control; Administrators full control; Trading traverse/list/read only | Trading cannot create, delete, rename, replace, change owner, change DACL, or write trust material. No inherited user or Everyone write ACE. |
| Bootstrap and signature | Administrators/SYSTEM | Administrators/SYSTEM read/write; Trading read-only if the approved release needs to read them | Trading has no write data, delete, rename, `WRITE_DAC`, or `WRITE_OWNER`. |
| `authority.sqlite3` | Administrators/SYSTEM | Administrators/SYSTEM full control; Trading read/write data and byte-range locking on this exact file | Trading cannot delete, rename, replace, change owner/DACL, or open a different final path as this file. |
| `authority.sqlite3-journal` | Administrators/SYSTEM | Administrators/SYSTEM full control; Trading read/write/truncate/lock on the pre-provisioned persistent rollback journal | Trading cannot delete, rename, replace, recreate, change owner/DACL, or create an alternate authoritative journal. |
| `capture-output\` | Administrators/SYSTEM | Administrators/SYSTEM full control; Trading may create and write capture outputs beneath the reviewed root | Trading cannot replace the root, alter its ACL, or use links/reparse points to escape it. |
| `backup\` | Administrators/SYSTEM | Administrators/SYSTEM full control only | Trading has no read, write, delete, or list access. |

The exact SQLite access contract is limited to opening the already named main
database and persistent rollback journal, reading pages, writing or truncating
those files as SQLite requires, obtaining and releasing SQLite byte-range
locks, flushing data, and querying file metadata. It does not include directory
deletion, database replacement, journal deletion or recreation, rename-based
installation, ACL changes, or access to backups. Provisioning must pre-create
the main database and persistent journal and validate that the selected
Python/SQLite build can operate with those exact rights. If journal
recreation, journal deletion, arbitrary directory creation, or another
unreviewed right is required, the deployment is a milestone blocker. The ACL
is not weakened automatically. A separately designed broker service is the
fallback architecture decision if a direct client cannot satisfy this ACL
contract.

The capture-output root may be writable only for bounded files created by the
approved release. Output filenames and final paths are validated against the
signed root and reparse-free final handles. Output bytes are evidence, never
authority.

### Fail-closed verification

At provisioning and every authority start, the release verifies for the
directory, bootstrap, signature, database, persistent journal, capture root,
and any selected output path:

- expected owner SID and exact DACL semantics;
- no reparse-point attribute on every component and final handle;
- `GetFinalPathNameByHandleW` equality with the pinned, normalized path;
- expected local volume and path prefix, without a UNC or alternate path; and
- no unauthorized hard-link or replacement condition detectable through the
  approved Windows handle checks.

An owner, ACE, reparse, final-path, volume, or access-right mismatch is a
typed fail-closed result. It does not fall back to a caller path or a copied
root.

## 4. SQLite authority model

### Common storage rules

All deterministic transactional IDs are lowercase UUID text produced with the
repository-owned UUID5 contract below. `machine_authority_id` and
`authority_epoch_id` are signed administrator-provisioned authority facts;
they may be UUID-formatted, but runtime implementations do not independently
derive them as UUID5 values. All digests are 32-byte SHA-256 values stored as
BLOBs, with canonical lowercase hex used only in human-readable diagnostics.
All policy, schema, provider, epoch, and operation fields are explicit
columns. UTC timestamps are facts, not identity inputs.

Canonical JSON evidence is stored as exact UTF-8 BLOBs in `*_json` columns;
the corresponding `*_digest` is stored beside it. Normalized columns hold
keys, foreign keys, state, ordinal, provider operation, policy versions,
epoch, disposition, and other fields required for constraints or indexed
state decisions. The normalized values must reconcile with the canonical JSON
before insertion. Raw provider bodies, credentials, environment dumps,
stdout, stderr, and arbitrary exception text are not stored.

Every table below includes `authority_epoch_id` and a foreign key to
`authority_metadata(authority_epoch_id)`, unless it is the metadata table
itself. Foreign keys are enabled for every connection.

### Tables and constraints

`authority_metadata` is a singleton deployment row:

```text
authority_metadata(
  authority_epoch_id TEXT PRIMARY KEY,
  machine_authority_id TEXT NOT NULL UNIQUE,
  bootstrap_schema INTEGER NOT NULL,
  bootstrap_generation INTEGER NOT NULL,
  signing_key_id TEXT NOT NULL,
  approved_account_sid TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  permitted_provider_operation TEXT NOT NULL,
  authority_policy_version TEXT NOT NULL,
  claim_policy_version TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  bootstrap_digest BLOB NOT NULL CHECK(length(bootstrap_digest)=32),
  database_identity_digest BLOB NOT NULL CHECK(length(database_identity_digest)=32),
  metadata_json BLOB NOT NULL,
  metadata_digest BLOB NOT NULL CHECK(length(metadata_digest)=32),
  CHECK(bootstrap_generation > 0)
)
```

It must contain exactly one row for the active epoch. Its values must match
the verified bootstrap before any transaction.

`database_identity_digest` is checked against the database-local metadata and
the currently verified bootstrap as a consistency binding. It is not an
external rollback anchor: because it is retained in the database, it cannot
prove freshness if the database and persistent journal are replaced together.

`schema_migrations` is an append-only record of the exact database schema:

```text
schema_migrations(
  migration_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  schema_version INTEGER NOT NULL,
  migration_policy_version TEXT NOT NULL,
  migration_digest BLOB NOT NULL CHECK(length(migration_digest)=32),
  application_release_digest BLOB NOT NULL CHECK(length(application_release_digest)=32),
  applied_at_utc TEXT NOT NULL,
  migration_json BLOB NOT NULL,
  UNIQUE(authority_epoch_id, schema_version)
)
```

The runtime accepts only the reviewed schema version. It does not run an
unreviewed migration or silently change this table.

`sessions` owns the session state and ordinal counter:

```text
sessions(
  session_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  session_schema INTEGER NOT NULL,
  authority_policy_version TEXT NOT NULL,
  target_session_date TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('OPEN','SUCCESS_SELECTED','CLOSED')),
  next_ordinal INTEGER NOT NULL CHECK(next_ordinal >= 0),
  session_request_json BLOB NOT NULL,
  session_request_digest BLOB NOT NULL CHECK(length(session_request_digest)=32),
  created_at_utc TEXT NOT NULL,
  closed_at_utc TEXT,
  close_reason TEXT,
  UNIQUE(authority_epoch_id, session_id)
)
```

`allocations` consumes one ordinal and is immutable after insertion except for
the controlled forward state field:

```text
allocations(
  allocation_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  session_id TEXT NOT NULL REFERENCES sessions,
  attempt_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
  state TEXT NOT NULL CHECK(state IN ('ALLOCATED_NOT_LAUNCHED','CLAIM_COMMITTED',
    'LAUNCH_RESERVED','LAUNCH_MAY_HAVE_OCCURRED','TERMINAL_RECORDED',
    'SUCCESS_SELECTED','CLOSED')),
  allocation_schema INTEGER NOT NULL,
  claim_policy_version TEXT NOT NULL,
  provider_call_budget INTEGER NOT NULL CHECK(provider_call_budget=1),
  provider_id TEXT NOT NULL,
  permitted_provider_operation TEXT NOT NULL,
  ordered_universe_digest BLOB NOT NULL CHECK(length(ordered_universe_digest)=32),
  request_json BLOB NOT NULL,
  request_digest BLOB NOT NULL CHECK(length(request_digest)=32),
  allocation_json BLOB NOT NULL,
  allocation_digest BLOB NOT NULL CHECK(length(allocation_digest)=32),
  allocated_at_utc TEXT NOT NULL,
  UNIQUE(authority_epoch_id, session_id, ordinal),
  UNIQUE(authority_epoch_id, session_id, attempt_id),
  UNIQUE(authority_epoch_id, allocation_id),
  FOREIGN KEY(authority_epoch_id, session_id) REFERENCES sessions(authority_epoch_id, session_id)
)
```

`provider_call_claims` is the permanent exactly-once fence:

```text
provider_call_claims(
  claim_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  allocation_id TEXT NOT NULL UNIQUE REFERENCES allocations,
  session_id TEXT NOT NULL REFERENCES sessions,
  attempt_id TEXT NOT NULL,
  claim_schema INTEGER NOT NULL,
  claim_policy_version TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  permitted_provider_operation TEXT NOT NULL,
  provider_call_budget INTEGER NOT NULL CHECK(provider_call_budget=1),
  request_json BLOB NOT NULL,
  request_digest BLOB NOT NULL CHECK(length(request_digest)=32),
  claim_digest BLOB NOT NULL CHECK(length(claim_digest)=32),
  committed_at_utc TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state='COMMITTED'),
  UNIQUE(authority_epoch_id, attempt_id),
  UNIQUE(authority_epoch_id, claim_id)
)
```

`launch_reservations` is the permanent transactional boundary between a
committed claim and process creation. Its reservation identity and binding
facts are immutable; only the explicitly controlled outcome state and
process-creation-failure evidence may move forward.

```text
launch_reservations(
  launch_reservation_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  session_id TEXT NOT NULL REFERENCES sessions,
  allocation_id TEXT NOT NULL REFERENCES allocations,
  attempt_id TEXT NOT NULL,
  claim_id TEXT NOT NULL UNIQUE REFERENCES provider_call_claims,
  launch_reservation_schema INTEGER NOT NULL,
  application_release_version TEXT NOT NULL,
  authority_policy_version TEXT NOT NULL,
  claim_policy_version TEXT NOT NULL,
  request_digest BLOB NOT NULL CHECK(length(request_digest)=32),
  reservation_json BLOB NOT NULL,
  reservation_digest BLOB NOT NULL CHECK(length(reservation_digest)=32),
  reservation_state TEXT NOT NULL CHECK(reservation_state IN
    ('COMMITTED','PROCESS_CREATED','PROCESS_CREATION_FAILED','MANUAL_REVIEW')),
  process_creation_failure_json BLOB,
  process_creation_failure_digest BLOB CHECK(
    process_creation_failure_digest IS NULL OR
    length(process_creation_failure_digest)=32),
  committed_at_utc TEXT NOT NULL,
  outcome_recorded_at_utc TEXT,
  UNIQUE(authority_epoch_id, session_id, allocation_id, attempt_id),
  UNIQUE(authority_epoch_id, launch_reservation_id),
  FOREIGN KEY(authority_epoch_id, session_id) REFERENCES
    sessions(authority_epoch_id, session_id),
  FOREIGN KEY(authority_epoch_id, allocation_id) REFERENCES
    allocations(authority_epoch_id, allocation_id),
  FOREIGN KEY(authority_epoch_id, attempt_id) REFERENCES
    allocations(authority_epoch_id, attempt_id)
)
```

The permanent `UNIQUE(claim_id)` constraint is the launch fence. A reservation
is inserted only for the exact committed claim, epoch, session, allocation,
attempt, request digest, application release, and policy versions. A
reservation winner is the only process permitted to call
`CreateProcessW(CREATE_SUSPENDED)`.

Triggers make the reservation identity and binding columns immutable, prohibit
deletion, and allow only forward outcome transitions. The
`PROCESS_CREATION_FAILED` state requires one sanitized failure JSON/digest;
`PROCESS_CREATED` requires the reservation-bound `launch_executions` row; and
`MANUAL_REVIEW` is absorbing until an administrator records the permitted
recovery fact. No outcome transition creates a second reservation or launch
attempt.

`launch_executions` contains the one process execution actually created by a
committed reservation. The phase columns are write-once facts; transitions can
only move forward:

```text
launch_executions(
  launch_execution_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  launch_reservation_id TEXT NOT NULL UNIQUE REFERENCES launch_reservations,
  claim_id TEXT NOT NULL UNIQUE REFERENCES provider_call_claims,
  allocation_id TEXT NOT NULL REFERENCES allocations,
  attempt_id TEXT NOT NULL,
  launch_schema INTEGER NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('PRE_RESUME_READY','RESUME_RECORDED',
    'POST_RESUME_AMBIGUOUS','TERMINAL_RECORDED','CLOSED')),
  process_creation_json BLOB NOT NULL,
  process_creation_digest BLOB NOT NULL CHECK(length(process_creation_digest)=32),
  resume_authorization_json BLOB NOT NULL,
  resume_authorization_digest BLOB NOT NULL CHECK(length(resume_authorization_digest)=32),
  post_resume_json BLOB,
  post_resume_digest BLOB CHECK(post_resume_digest IS NULL OR length(post_resume_digest)=32),
  normalized_pid INTEGER,
  normalized_job_assignment TEXT,
  normalized_resume_result TEXT,
  normalized_exit_code INTEGER,
  cleanup_json BLOB,
  cleanup_digest BLOB CHECK(cleanup_digest IS NULL OR length(cleanup_digest)=32),
  created_at_utc TEXT NOT NULL,
  UNIQUE(authority_epoch_id, attempt_id),
  FOREIGN KEY(authority_epoch_id, claim_id) REFERENCES
    provider_call_claims(authority_epoch_id, claim_id),
  FOREIGN KEY(authority_epoch_id, launch_reservation_id) REFERENCES
    launch_reservations(authority_epoch_id, launch_reservation_id)
)
```

`terminals` is an immutable final fact for the claim:

```text
terminals(
  terminal_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  claim_id TEXT NOT NULL UNIQUE REFERENCES provider_call_claims,
  allocation_id TEXT NOT NULL REFERENCES allocations,
  launch_reservation_id TEXT NOT NULL REFERENCES launch_reservations,
  launch_execution_id TEXT REFERENCES launch_executions,
  attempt_id TEXT NOT NULL,
  terminal_schema INTEGER NOT NULL,
  terminal_state TEXT NOT NULL CHECK(terminal_state IN ('SUCCEEDED','FAILED',
    'AMBIGUOUS','CLOSED')),
  provider_call_disposition TEXT NOT NULL CHECK(provider_call_disposition IN
    ('NOT_STARTED','CONFIRMED','MAY_HAVE_OCCURRED')),
  terminal_policy_version TEXT NOT NULL,
  request_digest BLOB NOT NULL CHECK(length(request_digest)=32),
  evidence_json BLOB NOT NULL,
  evidence_digest BLOB NOT NULL CHECK(length(evidence_digest)=32),
  snapshot_digest BLOB CHECK(snapshot_digest IS NULL OR length(snapshot_digest)=32),
  sanitized_diagnostics_json BLOB NOT NULL,
  recorded_at_utc TEXT NOT NULL,
  FOREIGN KEY(authority_epoch_id, launch_reservation_id) REFERENCES
    launch_reservations(authority_epoch_id, launch_reservation_id)
)
```

`SUCCEEDED` requires a confirmed response, independently verified snapshot,
and passing cleanup. `AMBIGUOUS` requires `MAY_HAVE_OCCURRED`; a resumed
timeout, crash, missing result, or unconfirmed termination cannot be marked
`NOT_STARTED`. `FAILED` cannot contain an accepted snapshot.

`selections` records the one success selected for a session:

```text
selections(
  selection_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  session_id TEXT NOT NULL REFERENCES sessions,
  terminal_id TEXT NOT NULL UNIQUE REFERENCES terminals,
  allocation_id TEXT NOT NULL REFERENCES allocations,
  attempt_id TEXT NOT NULL,
  selection_schema INTEGER NOT NULL,
  selection_policy_version TEXT NOT NULL,
  snapshot_digest BLOB NOT NULL CHECK(length(snapshot_digest)=32),
  selection_json BLOB NOT NULL,
  selection_digest BLOB NOT NULL CHECK(length(selection_digest)=32),
  selected_at_utc TEXT NOT NULL,
  UNIQUE(authority_epoch_id, session_id)
)
```

`manual_recoveries` is an immutable operator fact and authorization, never a
claim repair:

```text
manual_recoveries(
  recovery_id TEXT PRIMARY KEY,
  authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata,
  session_id TEXT NOT NULL REFERENCES sessions,
  target_allocation_id TEXT REFERENCES allocations,
  target_claim_id TEXT REFERENCES provider_call_claims,
  target_launch_reservation_id TEXT REFERENCES launch_reservations,
  target_terminal_id TEXT REFERENCES terminals,
  recovery_schema INTEGER NOT NULL,
  recovery_policy_version TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('RECORD_AMBIGUITY',
    'CLASSIFY_LAUNCH_RESERVATION','SELECT_COMMITTED_SUCCESS','CLOSE_SESSION',
    'ACKNOWLEDGE_RESTORE')),
  predecessor_state TEXT NOT NULL,
  resulting_state TEXT NOT NULL,
  recovery_ordinal INTEGER NOT NULL CHECK(recovery_ordinal >= 0),
  operator_evidence_json BLOB NOT NULL,
  operator_evidence_digest BLOB NOT NULL CHECK(length(operator_evidence_digest)=32),
  created_at_utc TEXT NOT NULL,
  UNIQUE(authority_epoch_id, recovery_id)
)
```

Foreign-key and trigger rules reject cross-epoch references, mismatched
session/allocation/claim/reservation/terminal identities, duplicate
allocations or launch reservations, updates to canonical facts, deletes,
state regressions, and transitions out of `SUCCESS_SELECTED` or `CLOSED`.
`provider_call_claims` and `launch_reservations` have no expiry, reclamation,
automatic deletion, or repair path. Every immutable table is append-only;
controlled state/counter updates are trigger-enforced and only write fields
that were explicitly left mutable. An integrity check treats any trigger
violation, orphan, duplicate, digest mismatch, or impossible state as
authority corruption.

### Deterministic identities

The repository owns one fixed UUID5 namespace for all deterministic
transactional identities:

```text
TRANSACTIONAL_IDENTITY_NAMESPACE_UUID =
  7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012
```

This constant is part of the release contract and never changes. Each identity
domain has its own material-version label, so a tuple change requires a new
label or a new repository-owned namespace. For a Unicode string `s`, define
the exact length frame as:

```text
LF(s) = ASCII(decimal number of UTF-8 bytes in s) + ":" + s
```

The UUID5 name is the UTF-8 encoding of the concatenation
`LF(material_label) || LF(field_1) || ... || LF(field_n)`. Integers use
canonical base-10 ASCII with no leading zeroes except `0`; UUIDs use lowercase
canonical text; dates use `YYYY-MM-DD`; booleans use `true` or `false`; an
optional value is represented by an explicit empty frame and is never omitted.
For an ordered list, define `UL(items) = LF(decimal item count) || LF(item_1)
|| ... || LF(item_n)` in caller-defined order; `UL(items)` is one field in the
outer tuple and is not replaced by a set or digest. The UUID5 result is
lowercased for storage.
This is a text/UTF-8 contract, not a language serializer contract.

The root session identity is exactly:

```text
session_id = UUID5(
  TRANSACTIONAL_IDENTITY_NAMESPACE_UUID,
  LF("session_id/v1") ||
  LF(machine_authority_id) ||
  LF(authority_epoch_id) ||
  LF(session_schema) ||
  LF(authority_policy_version) ||
  LF(claim_policy_version) ||
  LF("capture_request/v1") ||
  LF(target_session_date) ||
  LF(provider_id) ||
  LF(permitted_provider_operation) ||
  UL(ordered_universe) ||
  LF(bar_interval) ||
  LF(request_window_start_date) ||
  LF(request_window_end_date) ||
  LF(request_limit) ||
  LF(child_operation_version) ||
  LF(output_policy_version)
)
```

The fields are semantic request fields, not canonical JSON bytes, filesystem
paths, output names, or digests of serialized artifacts. The listed fields are
the complete `capture_request/v1` contract; a new semantic field requires a
new request/material version. Consequently, identical semantic session
requests under one authority epoch produce the same `session_id`, while a
different machine authority, epoch, policy, target date, provider, operation,
ordered universe, request limit, child operation, output policy, or other
versioned request meaning produces a different UUID5 input.

Every derived identity has a separate material label and exact tuple:

| Identity | Exact UUID5 tuple after the material label |
| --- | --- |
| `attempt_id` | `authority_epoch_id, session_id, ordinal, provider_id, permitted_provider_operation, claim_policy_version, capture_request/v1` |
| `allocation_id` | `authority_epoch_id, session_id, attempt_id, ordinal, allocation_schema, claim_policy_version, provider_id, permitted_provider_operation` |
| `claim_id` | `authority_epoch_id, allocation_id, attempt_id, claim_schema, claim_policy_version, provider_id, permitted_provider_operation, provider_call_budget` |
| `launch_reservation_id` | `authority_epoch_id, session_id, allocation_id, attempt_id, claim_id, launch_reservation_schema, application_release_version, authority_policy_version, claim_policy_version` |
| `launch_execution_id` | `authority_epoch_id, launch_reservation_id, claim_id, attempt_id, launch_schema, application_release_version, authority_policy_version` |
| `terminal_id` | `authority_epoch_id, claim_id, launch_reservation_id, launch_execution_id-or-empty, attempt_id, terminal_schema, terminal_policy_version` |
| `selection_id` | `authority_epoch_id, session_id, terminal_id, allocation_id, attempt_id, selection_schema, selection_policy_version` |
| `recovery_id` | `authority_epoch_id, session_id, target_allocation_id-or-empty, target_claim_id-or-empty, target_launch_reservation_id-or-empty, target_terminal_id-or-empty, action, predecessor_state, resulting_state, recovery_schema, recovery_policy_version, recovery_ordinal` |

The material labels are respectively
`attempt_id/v1`, `allocation_id/v1`, `claim_id/v1`,
`launch_reservation_id/v1`, `launch_execution_id/v1`, `terminal_id/v1`,
`selection_id/v1`, and `recovery_id/v1`. `recovery_ordinal` is an explicit
transactionally allocated domain ordinal, not database row order. Request
digests are stored and verified bindings, but are not substitutes for the
semantic identity tuple and are not identity inputs when they represent
serialized artifact bytes. No identity uses clocks, UUID4, Python hashes,
object identity, locale, filesystem paths, secrets, serialized artifact
bytes, or database row order. Distinct tuples have distinct UUID5 inputs;
the usual cryptographic collision assumption applies to the UUID5 result.

The unique `(authority_epoch_id, session_id, ordinal)` constraint and the
unique attempt, claim, and launch-reservation constraints make a second
allocation, claim, or launch reservation impossible even if two approved
processes race.

## 5. Transaction boundaries and crash outcomes

All write transactions below are `BEGIN IMMEDIATE` transactions on the fixed
database. They verify the current signed bootstrap digest, epoch, schema and
policy before changing state. They commit before an external side effect when
the boundary says so. A failed transaction rolls back its uncommitted changes;
it never rolls back a committed claim.

### Construct and reconcile the canonical request

Before any session or allocation write, the parent constructs the complete
nonsecret canonical request in memory from the verified bootstrap and the
fixed capture policy. It reconciles provider, operation, account/epoch,
ordered universe, target date, request limits, output root, child operation,
and all policy versions, then computes the request digest. This step does not
read credentials, create a process, contact a provider, or trust a caller
path. The exact in-memory request and digest are the values later bound by the
allocation and permanent claim.

### Session creation

1. Begin immediate.
2. Verify singleton metadata, current epoch, reviewed schema/policies, and the
   exact session request.
3. Insert one `OPEN` session with `next_ordinal=0` and its request digest.
4. Commit.

A crash before commit leaves no session. A crash after commit leaves the
session open and reusable by the same deterministic session identity after
exact verification. A duplicate session identity with different facts is a
conflict, not an overwrite.

### Allocate and consume an ordinal

1. Begin immediate and verify the session is `OPEN`, the epoch matches, and
   no success, closed state, or unresolved policy block prohibits allocation.
2. Read `next_ordinal`; construct the deterministic attempt and allocation
   identities.
3. Insert the immutable allocation with `provider_call_budget=1`.
4. Update `sessions.next_ordinal` by exactly one under the trigger rule.
5. Commit.

The allocation and ordinal consumption are one atomic decision. A crash before
commit consumes nothing. A crash after commit consumes the ordinal forever,
even if no child is launched. A unique conflict is treated as conflicting
authority; no alternate ordinal is silently selected.

### Create the permanent provider-call claim

1. Begin immediate.
2. Verify the allocation, request digest, provider operation, claim policy,
   session state, and authority epoch.
3. Insert the one `COMMITTED` row into `provider_call_claims`, relying on
   `UNIQUE(allocation_id)` and the attempt uniqueness constraint.
4. Advance the allocation to `CLAIM_COMMITTED`.
5. Commit.

This transaction must commit before current-process SID access, Credential
Manager reads, provider construction, or network access. There is no delete,
expiry, repair, reclamation, or retry that creates another claim. A crash
before commit permits the exact claim transaction to be retried because no
provider side effect is allowed before commitment. A crash after commit is
permanent authority: the process may not assume that no provider call occurred.

### Reserve the launch before creating a process

1. Begin immediate.
2. Verify the singleton metadata, permanent committed claim, exact epoch,
   session, allocation, attempt, canonical request, request digest, release
   version, and policy versions. Verify that the claim has no committed launch
   reservation and that no absorbing state or manual-review block permits a
   launch.
3. Construct the deterministic `launch_reservation_id` and insert exactly one
   `launch_reservations` row. The permanent `UNIQUE(claim_id)` constraint is
   the authority fence.
4. Advance the allocation to `LAUNCH_RESERVED` and commit the reservation
   before any process-creation call.

Only the process that commits this reservation may call
`CreateProcessW(CREATE_SUSPENDED)`. A concurrent loser stops before process
creation after a deterministic unique-conflict or already-reserved result; it
does not create a second reservation, launch attempt, child, or provider call.
A crash before reservation commit rolls back the reservation and permits the
same deterministic reservation transaction to be retried. A crash immediately
after reservation commit and before `CreateProcessW` leaves the claim and
reservation permanently consumed; it requires manual classification and does
not authorize another automatic launch.

### Create the process and record pre-resume launch facts

1. The reservation winner calls `CreateProcessW` with `CREATE_SUSPENDED` using
   the already committed request. If process creation fails, begin immediate,
   verify the existing reservation, and record the exact sanitized failure
   evidence against that reservation. Advance its controlled outcome to
   `PROCESS_CREATION_FAILED` and record a failed, non-retried terminal without
   creating a second reservation, launch attempt, or `launch_executions` row.
   The committed claim remains consumed.
2. For a created process, assign it to the Job Object and verify the Job
   assignment, active-process limit, kill-on-close policy, and no-inherited-
   handle posture.
3. Begin immediate and verify the committed reservation, claim, and exact
   canonical request.
4. Insert the one `launch_executions` row, including the committed
   `launch_reservation_id`, exact process creation, executable/release
   digests, Job Object assignment, constrained environment digest, resume
   authorization, and all sanitized native facts available before resume.
5. Advance the reservation outcome to `PROCESS_CREATED` and commit with
   `phase=PRE_RESUME_READY`.

Only after this commit may the launcher call `ResumeThread`. A crash after
reservation commit but before process creation leaves a consumed reservation
with no process and no retry authorization. A crash after process creation or
Job assignment but before the launch-evidence commit leaves a consumed
reservation with incomplete facts; it is manual review, not automatic claim
or reservation reuse. A crash after the evidence commit but before resume can
be proven zero-call only by a later explicit native evidence review that
proves the child remained suspended and was terminated. The database itself
does not infer that proof.

### Record post-resume ambiguous facts

After resume, or when the launcher cannot prove a clean pre-resume outcome:

1. Begin immediate and verify `PRE_RESUME_READY`, claim, attempt, and process
   identities.
2. Write the post-resume/timeout/termination facts once, including bounded
   exit and cleanup evidence, and advance the phase to
   `POST_RESUME_AMBIGUOUS`.
3. Commit.

A crash before this commit does not make the attempt reusable. On restart, a
committed claim with a missing post-resume row is conservatively treated as
possibly resumed and requires manual review. A crash after commit preserves an
ambiguous fact that cannot authorize another provider call.

### Record successful or failed terminal facts

1. Begin immediate and verify the claim, launch evidence, request digest, and
   exact provider disposition.
2. Insert one immutable `terminals` row with canonical evidence and sanitized
   diagnostics.
3. Advance the allocation to `TERMINAL_RECORDED`.
4. Commit.

`SUCCEEDED` is admitted only with a confirmed response, an independently
verified exact snapshot, and exactly-once credential/handle cleanup. A
post-resume timeout, crash, missing result, or unconfirmed termination is
`AMBIGUOUS`, not `FAILED` or `NOT_STARTED`. If the process crashes before
terminal commit, the committed claim remains ambiguous; a snapshot found on
disk is evidence only until a terminal or manual selection is recorded.

### Select success

1. Begin immediate and verify the session is `OPEN`, the terminal is the
   pointer-equivalent database fact `SUCCEEDED`, the snapshot digest matches,
   and no selection exists.
2. Insert the unique `selections` row with explicit selection-policy evidence.
3. Advance the allocation and session to `SUCCESS_SELECTED`.
4. Commit.

A crash before commit leaves a valid but unselected success requiring explicit
manual review; it does not reopen the attempt or run readiness again. After
commit, `SUCCESS_SELECTED` is absorbing and no allocation, selection, repair,
or recovery can alter it.

### Close a session

1. Begin immediate and verify no unreviewed allocation or claim is being
   silently abandoned. Any unresolved claim requires an explicit manual
   recovery record.
2. Write the close fact and advance the session to `CLOSED`; controlled
   completed allocations may also advance to `CLOSED`.
3. Commit.

A crash before commit leaves the prior state authoritative. After commit,
`CLOSED` is absorbing. It is never reopened for a call.

### Manual recovery

1. Begin immediate and verify the current epoch, target digests, predecessor
   state, operator evidence, recovery policy, and requested action.
2. Insert one immutable `manual_recoveries` row.
3. Apply only the action's allowed state transition: record ambiguity,
   classify a consumed launch reservation (including a reservation with no
   known process after a crash), select an already committed and verified
   success, close a session, or acknowledge an administrator-approved restore.
   Reservation classification never deletes, resets, or reopens the
   reservation and never authorizes another launch or provider call.
4. Commit.

Manual recovery never creates or deletes a claim, invokes a provider, changes
canonical evidence, or converts uncertainty into `NOT_STARTED`. A crash
before commit leaves the predecessor state. A crash after commit leaves the
manual fact and resulting absorbing state together.

## 6. SQLite durability and concurrency

- `journal_mode=PERSIST` is the initial reviewed design. The main database and
  persistent rollback journal are provisioned in advance and remain the only
  authority files used by SQLite.
- `synchronous=FULL` is required. A commit is not reported successful until
  SQLite's full durability contract completes; `NORMAL`, `OFF`, or an
  environment-controlled override is not accepted.
- `PRAGMA foreign_keys=ON` is required on every connection. A connection that
  cannot prove it is enabled is rejected.
- There is one authority database only. `ATTACH`, `VACUUM`, runtime DDL, and
  automatic migration are prohibited. The reviewed schema is selected during
  administrator provisioning and checked at startup.
- A bounded `busy_timeout` of 5 seconds applies to `BEGIN IMMEDIATE` lock
  waits before claim commitment. It is a lock-wait policy, not an authority
  retry policy. The timeout and exact Python/SQLite build are recorded in
  sanitized authority diagnostics.
- Only the named pre-claim transactions may retry `SQLITE_BUSY` or
  `SQLITE_LOCKED`: a bounded number of fresh `BEGIN IMMEDIATE` attempts using
  the same deterministic inputs. The retry is allowed only while no claim has
  committed and no provider side effect has occurred.
- The launch-reservation transaction is post-claim and is attempted once for
  that committed claim. A busy result, unique conflict, or existing
  reservation stops that runner before process creation; it is never converted
  into a new reservation or automatic launch retry.
- There is no generic transaction decorator or automatic retry loop. After a
  claim commits, no provider-attempt retry is permitted. A later database
  write may be retried only as an explicitly idempotent persistence operation
  for the same already-known evidence identity; it must never reconstruct or
  re-run a provider attempt.
- SQLite locking assumes one local NTFS volume, no SMB/UNC path, no cloud
  sync, no copied live database, and all participants use the exact reviewed
  Python/SQLite build, PERSIST behavior, and ACL. A different locking
  environment is NO-GO.
- Authority start and recovery run `PRAGMA quick_check`,
  `PRAGMA foreign_key_check`, and the reviewed schema/trigger checks. A
  scheduled full `PRAGMA integrity_check` is required before promotion and
  after historical restore validation. Any result other than `ok`, any
  persistent-journal mismatch, or any digest or epoch mismatch fails closed.
  No automatic repair is permitted. Failure of PERSIST mode under the
  approved ACL is a Milestone B blocker; directory permissions are not
  weakened to compensate.

### Backup requirements

An administrator performs a consistent SQLite online backup, or a fully
quiesced reviewed file backup, and records the backup result, database digest,
bootstrap digest/generation, schema version, and application release digest in
an administrator-only manifest. The signed bootstrap and detached signature
are copied with that manifest; the offline signing private key is never
copied.

A fully quiesced file backup stops all authority writers, verifies that no
transaction is active, copies the main database and its persistent rollback
journal as one reviewed set, and validates the copy with SQLite integrity and
digest checks. A main-file-only copy or a copy while the journal is active is
invalid. The procedure never deletes or recreates the live journal to make a
backup appear clean.

## 7. Child and launcher integration

The integration retains the existing safety concepts:

- the parent remains secret-free and rejects Alpaca variables in its own
  environment;
- only the child performs the exact current-process SID gate and reads the two
  named Credential Manager entries;
- one provider instance and one provider-call fence are created in the child,
  with no retry, pagination continuation, fallback endpoint, or second call;
- the parent commits a unique launch reservation for the claim before calling
  suspended `CreateProcessW`; only its reservation winner may create the
  child, assign and verify it in a Job Object with kill-on-close and
  active-process limit one, record exact process creation and
  resume-authorization facts transactionally, commit those facts, and only
  then call `ResumeThread`;
- no handles are inherited and the child receives only the constrained
  reviewed environment;
- any uncertainty after resume is ambiguous and never a zero-call proof;
- native credential release occurs exactly once across all success and failure
  paths, with the full valid native blob range cleared before `CredFree`; and
- every owned process, thread, Job Object, and native resource handle is
  cleaned up unconditionally, with only stable sanitized diagnostics retained.

The transaction sequence is:

```text
signed bootstrap and path/ACL verification
  -> canonical request construction and in-memory reconciliation
  -> session verification and ordinal-allocation transaction
  -> permanent request-bound claim transaction and commit
  -> unique launch-reservation transaction and commit
  -> reservation winner calls CreateProcessW(CREATE_SUSPENDED)
  -> Job Object assignment and verification
  -> reservation-bound process-creation/resume-authorization transaction and commit
  -> ResumeThread
  -> post-resume fact transaction, or conservative missing-fact ambiguity
  -> terminal transaction
  -> success-selection transaction, if eligible
```

Launcher/process evidence is represented by the normalized
`launch_reservations` row, any reservation-bound process-creation failure
evidence, and the normalized `launch_executions` row plus its canonical
creation, resume, post-resume, and cleanup evidence blobs and digests.
`launch_executions` exists only when the reservation winner actually created a
process. Terminal evidence stores the sanitized child result, provider
disposition, snapshot digest, and cleanup result. The database rows are the
single transactional authority. Temporary request or output files may be
transport artifacts, but no mutually validating claim/history file web is
executable and no directory scan can create authority.

## 8. Compatibility and migration

Schema-1 and schema-2 JSON artifacts from the existing milestones remain
parseable for historical validation only. Historical validation may verify
their canonical bytes, UUID5 identities, predecessor relationships, and
legacy diagnostics, but it must not import them as executable provider
authority.

The selected compatibility decision is a new `authority_epoch_id` with no
executable migration. Provisioning creates a new empty SQLite authority and a
new signed bootstrap generation/epoch. Existing file-based allocations,
claims, history heads, terminals, and recovery files are retained as
historical evidence and are never consumed to authorize a provider call.

The current file-based provider-call claim system is not an executable
fallback. If the SQLite authority is unavailable or invalid, the capture is
blocked; it does not switch to claim files, choose a highest ordinal, or infer
authority from legacy artifacts.

## 9. Backup and recovery

### Restore and rollback validation

Restore is administrator-only and begins by preserving the failed database and
the persistent journal for forensic review. The candidate backup is restored
to an isolated staging path, then validated as historical evidence for exact
owner/DACL/reparse/final-path semantics, independently retained signed
bootstrap generation and digest, machine authority, epoch, schema migrations,
SQLite integrity, foreign keys, canonical evidence digests, state
transitions, claims, and ambiguity facts. It is never made executable by
copying it over the live path.

Rollback rejection is required only where independently retained trusted state
can show a mismatch: an older-generation database, an epoch that does not
match the current signed bootstrap, altered bootstrap or signature material,
copied roots, and path aliases. A database-local digest, including
`database_identity_digest`, is a consistency check and not an external
freshness anchor. If the database and persistent journal are completely
replaced with an internally consistent same-generation pair, the database
cannot prove that replacement from its own contents. Replacement by
Administrator/SYSTEM, malicious direct database modification by `Trading`,
and arbitrary code controlling that account remain outside the stated threat
model; no external service or monotonic hardware anchor is added here.

Every administrator-approved restore is epoch-reset only. After historical
validation, the administrator must rotate the signed `bootstrap_generation`,
create a new `authority_epoch_id`, and provision a new empty executable
authority database. The old database and all of its allocations, claims,
terminals, selections, and ambiguity facts remain preserved as historical
evidence. No restored database may resume executable operation under its old
epoch, and no old row may be imported or reused as executable provider
authority.

### Unavailable or corrupt material

- Missing, unreadable, unsigned, mismatched, or invalid bootstrap/signature:
  stop before database mutation, process creation, SID access, Credential
  Manager access, provider construction, or transport.
- Missing, unreadable, locked-inconsistently, corrupt, or mismatched database
  or persistent journal: do not create a new database at the pinned path,
  delete or recreate the journal, repair in place, or call a provider.
  Preserve the evidence and invoke administrator recovery.
- Missing or unverifiable backup: the deployment cannot pass the operational
  backup gate. A manual development validation may inspect the authority only
  if its policy explicitly permits it; it may not perform provider capture.
- Capture-output root unavailable or outside its final pinned path: no
  provider call is authorized because a verified result cannot be committed.

If no valid backup exists, recovery is still a new administrator-reviewed
signed bootstrap and new authority epoch with an empty executable database.
The operator must preserve the failed database as historical evidence and
record that prior claims may be unknown; the system never infers that a
committed claim did not occur.

## 10. Milestones and acceptance gates

### A. Bootstrap and provisioning

**Deliverables:** canonical bootstrap and detached-envelope specification;
CNG P-256 verification design and vectors; fixed-path/final-path checks;
owner/DACL/reparse contract; administrator provisioning and rotation runbook.

**Non-goals:** SQLite transactions, provider construction, Credential Manager
reads, capture, scheduling, live trading, or unattended approval.

**Focused tests:** canonical field rejection, signature verification and key
ID mismatch, generation/epoch binding, path traversal/reparse rejection,
owner/DACL decision tests, and release-key vector tests.

**Manual Windows validation:** provision on a local NTFS volume; inspect owner,
explicit ACEs, inheritance, final paths, persistent journal, and the Trading account's
denied writes/replacements; test a copied root and junctioned path.

**Exit criteria:** the approved release accepts only the signed fixed bootstrap;
all path and ACL checks fail closed; the Trading account cannot replace trust
material or the authority directory; and the provisioning evidence is
administrator-reviewed.

**Remaining NO-GO:** any unsigned/rotated-key ambiguity, writable trust
material, reparse path, unsupported CNG verifier, or unattended launch.

### B. Transactional authority database

**Deliverables:** reviewed SQLite schema, constraints and triggers; repository
transaction contract; epoch binding; canonical evidence/digest rules; backup
and restore manifest contract.

**Non-goals:** provider calls, child credentials, scheduler, live brokerage,
automatic migrations, claim-file fallback, or runtime implementation in this
documentation milestone.

**Focused tests:** exact deterministic identity vectors for the root session and
every derived identity; schema/foreign-key/trigger checks; concurrent
session/ordinal allocation; duplicate claim and launch-reservation races;
crash-injected boundaries; PERSIST durability and journal lifecycle;
integrity checks; backup/restore; and fail-closed rejection of rollback cases
that conflict with independently retained signed/bootstrap state.

**Manual Windows validation:** run multiple approved processes under the
dedicated account; inspect PERSIST journal locking and ACLs; stop/kill at each
transaction boundary; validate that journal recreation and directory rights
are not required; validate a restored database and intentionally older,
copied-root, and path-alias databases. The validation records the explicit
limitation that an internally consistent same-generation database/journal
replacement cannot be detected without independent trusted state.

**Exit criteria:** one allocation has at most one permanent claim; claim
commit precedes all provider-side effects; ambiguity survives all crash
points; success and closed states are absorbing; no generic retry or repair
exists; and backup/restore evidence is reproducible.

**Remaining NO-GO:** any duplicate claim or launch reservation, claim or
reservation deletion/expiry, state regression, PERSIST failure under the
approved ACL, journal recreation requirement, unreviewed migration, a
detectable rollback accepted despite an independently retained signed-state
mismatch, or an authority decision based on a legacy file. Same-generation
replacement by an out-of-boundary privileged actor is not represented as a
guarantee of this milestone.

### C. Child/launcher integration

**Deliverables:** transaction-bound child request and process evidence model;
permanent claim and launch-reservation boundary; pre-resume and post-resume
recording; one-call provider fence; SID and Credential Manager boundary; Job
Object, handle, environment, and cleanup contract.

**Non-goals:** unattended scheduling, automatic retry, paper-lineage advance,
provider fallback, or real-money trading.

**Focused tests:** exactly-one provider call; two-runner launch-reservation
races proving one reservation and no losing `CreateProcessW`; crash before and
after reservation commit, before process creation, and after process-creation
failure; duplicate/concurrent launch attempts; crash before/after claim and
resume; SID mismatch; child-only credential reads; native cleanup; sanitized
malicious responses; suspended creation, Job containment, no inherited handles,
and unconditional handle cleanup.

**Manual Windows validation:** dedicated non-administrative account, real
`CreateProcessW`/Job Object behavior with test-only nonsecret fixtures, ACL
and environment inspection, forced termination, and post-resume ambiguity
review. Any provider-connected exercise requires separate explicit approval
and must remain a single manually initiated call.

**Exit criteria:** parent memory and environment are secret-free; exactly one
claim maps to exactly one permanent launch reservation; exactly one
reservation-bound child/provider fence can exist; the losing runner never
calls `CreateProcessW`; evidence is transactional; resume uncertainty is never
reused; and cleanup is proven on every path.

**Remaining NO-GO:** any secret in parent/output, SID bypass, second call,
credential cleanup gap, handle leak, inherited handle, process escape, or
automatic ambiguity retry.

### D. Manual dedicated-account end-to-end validation

**Deliverables:** administrator-reviewed runbook, evidence bundle format,
operator sign-off form, backup-before-run proof, and manual recovery procedure.

**Non-goals:** unattended scheduling, scheduler installation, always-on service,
automatic recovery, live-money orders, or approval inferred from a passing
single run.

**Focused tests:** full session-to-selection transaction, failed and ambiguous
terminal paths, duplicate invocation, backup/restore, rollback, output digest
verification, and manual committed-success selection.

**Manual Windows validation:** execute only from the approved Trading account
with the fixed bootstrap and local NTFS paths; inspect ACLs and final paths;
perform one explicitly authorized manual capture attempt; verify exactly one
provider call if a provider-connected test is separately approved; and review
all sanitized evidence and cleanup facts.

**Exit criteria:** the runbook demonstrates durable authority, exact account
binding, one-call behavior, truthful ambiguity, recoverable backups, and no
file-based fallback. This is still manual-only.

**Remaining NO-GO:** unresolved official XNYS-hours authority, weak launch
guard DACL, missing trusted process/time evidence, missing monitoring,
unverified restore, or any scheduler/account-rights gap.

### E. Later operational prerequisites

**Deliverables:** separately reviewed hardened launch-guard DACL; official
XNYS-hours authority; trusted time/process evidence; monitoring and
notification; backup and restore operations; scheduler configuration and
account-rights review.

**Non-goals:** this architecture milestone does not approve unattended
operation or real-money trading.

**Focused tests:** launch-guard contention and DACL tests, official-hours
provenance tests, trusted-evidence freshness/rollback tests, notification
failure tests, backup restore drills, and scheduler least-privilege tests.

**Manual Windows validation:** administrator-led review of the scheduler,
account token, task ACLs, service/interactive-session behavior, monitoring
alerts, restore drill, and controlled out-of-hours refusal.

**Exit criteria:** each prerequisite has independent evidence and explicit
approval; no single successful capture substitutes for operational controls.

**Remaining NO-GO:** unattended scheduling remains NO-GO until all of the
following are separately approved: hardened launch-guard DACL; official
XNYS-hours authority; trusted time/process evidence; monitoring and
notification; backup and restore; and scheduler configuration and account
rights.
