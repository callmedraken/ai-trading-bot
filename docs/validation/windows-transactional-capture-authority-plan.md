# Windows transactional capture authority validation plan

This plan is evidence for the architecture in
`docs/architecture/77-windows-transactional-capture-authority.md`. It is a
future validation plan, not an implementation or an approval for unattended or
provider-connected operation. Tests use fake providers, fake Credential
Manager/native adapters, crash injection, temporary test databases, and
dedicated Windows accounts unless a row below explicitly requires a manual
administrator check. No test may use real-money trading or place a real order.

## Evidence rules

- Every test records the release digest, bootstrap generation, authority epoch,
  schema version, SQLite version, journal/synchronous settings, and sanitized
  diagnostics.
- Tests compare canonical bytes and SHA-256 digests, not object equality or
  filesystem discovery. Paths are transport inputs and never identity inputs.
- Deterministic identity tests use the fixed repository namespace, exact
  material labels, and exact length-framed semantic tuples. They include a
  golden vector for the root `session_id` and for every derived identity:
  `attempt_id`, `allocation_id`, `claim_id`, `launch_reservation_id`,
  `launch_execution_id`, `terminal_id`, `selection_id`, and `recovery_id`.
  Each vector records the exact framed UTF-8 preimage and expected lowercase
  UUID5 result so a test cannot pass by merely recomputing the implementation.
- A crash test preserves the database, persistent rollback journal, bootstrap,
  signature, and output evidence for inspection. It never deletes a committed
  claim to make the next run pass.
- The dedicated Trading account and approved processes running under its token
  are trusted participants in the architecture. Validation covers accidental
  duplicate/cooperating approved processes and other Windows accounts; it does
  not claim to protect against a compromised Trading account, arbitrary code
  under that token, or direct malicious database modification by that account.
- Rollback validation distinguishes mismatches visible through independently
  retained signed/bootstrap state, administrator-approved historical-only
  restores, and complete same-generation replacement by Administrator/SYSTEM
  or trusted-token code. The last case is outside the trust boundary and has
  no expected detection result; no external service or monotonic anchor is
  introduced by this milestone.
- Windows manual checks run on a local NTFS volume under the dedicated
  non-administrative Trading account and repeat administrator checks under an
  administrator account. No test grants Trading administrator rights.
- A passing focused test is not an operational approval. Unattended scheduling
  remains NO-GO until the separately listed prerequisites are approved.

## Invariant-to-evidence matrix

| Architecture invariant | Planned automated evidence | Planned manual Windows evidence | Failure meaning |
| --- | --- | --- | --- |
| Only the fixed `F:\AITradingBot\Authority\` bootstrap path is executable | Verify caller config, CLI, environment, database rows, copied roots, and alternate absolute paths cannot change the bootstrap/database/output paths; assert the release constant is used | Move/copy the tree, invoke from another current directory, supply junctioned and UNC-like paths, and verify the fixed deployment is the only accepted location | Any caller-selected authority path is a security failure |
| Bootstrap canonical fields, generation, epoch, SID, policy, provider, operation, and provisioning timestamp are exact | Golden canonical JSON/UUID/digest vectors; reject missing, extra, duplicate, float, path-alias, invalid-SID, and noncanonical timestamp fields | Provision two generations and inspect that the exact values are bound to the machine, account, database, and output root | Field drift or identity dependence on a runtime clock invalidates the bootstrap |
| Detached signature and pinned key are required | Valid CNG P-256 vector; wrong key ID, wrong digest, malformed signature, altered byte, old key, and absent signature all fail before SQLite mutation | Replace bootstrap/signature as Trading, alter bytes as administrator, and confirm no DB write, process creation, SID access, Credential Manager access, provider construction, or transport occurs | Any side effect before verification is a NO-GO |
| Trust boundary excludes compromised Administrator/SYSTEM, release replacement, signing-key compromise, and kernel compromise | Documented negative security assumptions and release/key identity checks | Administrator-led compromise/re-provisioning drill records that the system stops and requires a new approved release/epoch | The design must not claim to mitigate these conditions |
| Trusted-account boundary is explicit | Verify that approved-process identity and token assumptions are documented, while SQLite constraints are treated only as serialization/integrity controls and not executable authentication | Review the Trading token, approved process launch path, and scope statement; record that hostile same-account code requires a separately designed broker service | Any claim that SQLite authenticates an executable or protects against compromised same-account code is rejected |
| Direct malicious same-Trading-account behavior is out of scope | Negative documentation/security-review evidence confirms no hostile same-token guarantee is tested as a security property | Attempted malicious same-account database modification may be recorded as an out-of-scope limitation, not as a passing protection test | The architecture must not overclaim same-account isolation |
| Owner, DACL, inheritance, reparse, final-path, and local-volume requirements hold | ACL decision tests for missing/extra ACEs, inherited write, wrong owner, reparse metadata, path mismatch, UNC/volume mismatch, and inaccessible handles | Inspect every object with Windows security tools; attempt Trading writes, deletes, renames, ACL changes, bootstrap replacement, directory replacement, junction creation, and copied-root execution | Any writable trust material or path alias is a fail-closed result |
| Trading has only exact SQLite and capture-output rights | Access tests assert permitted database page/persistent-journal/lock operations and denied trust/backup operations | Run the authority as Trading; verify bootstrap is readable, database and pre-created journal are writable/lockable, backup is inaccessible, and directory replacement is denied | An ACL workaround that grants broad directory rights is not accepted |
| Authority metadata binds machine, epoch, bootstrap generation/digest, SID, policy, schema, and database identity | Insert altered metadata, cross-epoch rows, wrong generation, wrong digest, or wrong release digest and assert startup/transaction rejection; verify `database_identity_digest` is treated only as a database-local consistency field, never as an external freshness anchor | Restore a metadata-mismatched database and inspect the typed refusal; record that a complete internally consistent same-generation replacement has no expected detection result without independent trusted state | Mismatched authority metadata is corruption, not a repair prompt; same-generation privileged replacement remains outside the threat model |
| Schema migrations are reviewed, append-only, and exact | Verify primary/foreign keys, unique constraints, check constraints, migration digest, one active schema, no runtime DDL, and no unreviewed migration | Start with an older or extra migration row and verify the release refuses operation | Automatic schema evolution is prohibited |
| Proposed authority DDL has executable foreign-key integrity | Execute the complete proposed SQLite DDL in a temporary database with `PRAGMA foreign_keys=ON`; insert one valid metadata/session/allocation/claim/reservation chain; assert the valid `launch_reservations` insert succeeds, mismatched epoch/session/allocation/attempt combinations are rejected, `PRAGMA foreign_key_check` returns no rows, and reservation insertion never raises `foreign key mismatch` | Run the DDL smoke script with the reviewed SQLite build and retain the schema plus `foreign_key_check` output as evidence | Any invalid parent-key sequence, accepted mismatched composite binding, `foreign_key_check` row, or foreign-key mismatch is a schema NO-GO |
| Canonical JSON evidence is preserved; normalized columns reconcile | Round-trip exact BLOB bytes/digests; mutate normalized columns or evidence separately; reject secrets, raw bodies, environment, stdout, stderr, and arbitrary exceptions | Inspect an authority DB and evidence bundle for exact canonical bytes and sanitized diagnostics | Evidence mutation or secret retention invalidates the record |
| Deterministic identities and ordinal uniqueness are stable | Verify the fixed repository UUID5 namespace, exact length framing, and golden vectors for `session_id`, `attempt_id`, `allocation_id`, `claim_id`, `launch_reservation_id`, `launch_execution_id`, `terminal_id`, `selection_id`, and `recovery_id`; same semantic inputs across paths/processes yield the same IDs; clock/UUID4/hash/object/path/serialized-byte perturbations do not change identity; changing epoch, policy, date, provider, operation, or request semantics changes the UUID5 input; duplicate `(epoch,session,ordinal)` fails | Repeat the root session and every derived identity from different directories and processes, with altered environment values and path spellings, and compare IDs/digests | Identity instability, an omitted semantic field, or duplicate ordinal is a NO-GO |
| Session creation is atomic | Crash before/after session commit; duplicate exact session and conflicting session tests | Kill the process during session creation and inspect the database and persistent journal | Partial session facts or overwrite is a failure |
| Allocation consumes one ordinal atomically | Concurrent `BEGIN IMMEDIATE` allocation race; crash before and after commit; unique ordinal/attempt checks | Run two Trading processes against one session and inspect one committed allocation per ordinal | Lost, reused, or silently skipped ordinals are failures |
| Exactly one permanent provider-call claim exists per allocation | Concurrent duplicate-claim race; `UNIQUE(allocation_id)` and attempt uniqueness; claim deletion/expiry/reclamation/repair attempts fail | Kill/restart around claim commit and verify the committed row remains and cannot be replaced | A second claim or claim deletion is a NO-GO |
| Claim commit precedes SID, credential, provider, and network effects | Instrument fake native credential/provider/transport constructors and assert no call before claim commit; crash injection between every precondition | Observe process and Credential Manager audit/test hooks around the boundary | Any provider-side effect before a durable claim is a security failure |
| Canonical request is constructed and reconciled before session/allocation/claim work | Supply conflicting caller config, paths, policy, provider, operation, universe, output, and epoch values; assert one canonical in-memory request/digest is formed before any authority write | Review a trace showing fixed bootstrap verification, in-memory request reconciliation, then session/allocation, then claim; verify no credential or process access occurs during construction | Request reconciliation after claim commitment or authority based on caller-selected paths is a failure |
| Safe lock retries occur only before claim acquisition | Hold the DB lock during session/allocation/pre-claim operations and verify bounded same-input retry; test lock after claim and assert no provider-attempt retry | Use two Windows processes to hold locks and inspect retry diagnostics and absence of duplicate calls | Generic retry loops are prohibited |
| Transactional launch reservation permits only one process creator | Fake two independent runners with one committed claim; both execute `BEGIN IMMEDIATE` reservation logic; assert exactly one immutable `launch_reservations` row commits because of permanent `UNIQUE(claim_id)`, only its winner may call `CreateProcessW(CREATE_SUSPENDED)`, and the losing runner stops before process creation; bind the row to exact epoch/session/allocation/attempt/request digest/release/policy values | Race two approved runners and inspect one reservation, one process-creation invocation, no losing invocation, and no provider call from either loser path | Two reservations, a losing `CreateProcessW`, reservation reuse, or any provider call from the loser is a NO-GO |
| Process creation, Job verification, evidence commit, and resume have the required order | Fake `CreateProcessW`, Job, database, and `ResumeThread` adapters; assert the reservation commits first, the winner calls `CreateProcessW`, Job assignment is verified second, exact creation/resume facts are recorded against the committed reservation third, and only then is `ResumeThread` invoked; inject creation failure and record it against the existing reservation without a second reservation or `launch_executions` row | Opt-in real suspended process check verifies reservation, creation, Job assignment, transactional evidence commit, and resume order; inspect that no evidence is published before process creation | Any process creation before reservation, evidence publication before process creation, process execution without a reservation, request reconciliation after claim, resume before evidence commit, or reservation/claim reuse after creation failure is a NO-GO |
| Post-resume uncertainty is conservative | Inject crash after `ResumeThread`, during timeout, after termination request, before post-resume commit, and after commit; all cases remain ambiguous/manual | Force termination and kill the parent after resume; inspect that no same-attempt reuse or automatic retry is authorized | Any ambiguous attempt reused as `NOT_STARTED` is a failure |
| Terminal facts are immutable and typed | Success requires confirmed response, verified snapshot, exit/cleanup success; failed terminal rejects accepted snapshot; timeout/crash/missing result maps to ambiguous | Inspect terminal rows after provider/child failures and manual review | A terminal that overclaims success or no-call is invalid |
| Exactly one provider call is fenced | Fake provider counts construction and transport calls; second fetch, pagination, reconnect, fallback endpoint, and retry all fail before transport | If separately approved, run one manually initiated provider-connected capture and verify provider-side call count plus local fence evidence | More than one provider call is a NO-GO |
| Parent remains secret-free and child owns credential reads | Seed parent env/config/CLI with hostile credential-like values; assert rejection and unchanged environment; fake Credential Manager asserts exact child SID gate and target reads | Inspect parent process/environment and child token; attempt wrong SID and wrong target/persistence/type/size values | Secret crossing or SID bypass is a security failure |
| Credential and native cleanup is exactly once | Inject success, missing, malformed, oversized, null, overflow, decoding, provider, timeout, and exception paths; assert full native range clearing, one `CredFree`, redaction, and dropped references | Use Windows test-only Credential Manager targets and native tracing under the dedicated account; verify no writes/enumeration/deletion | Any cleanup omission, double release, or secret diagnostic is a NO-GO |
| Process containment and cleanup are unconditional | Fake and opt-in real `CreateProcessW`/Job adapters verify suspended creation, active-process limit one, kill-on-close, no inherited handles, bounded streams, and all handle closes | Inspect Job membership, process tree, handles, environment allowlist, and forced termination behavior | Process escape or leaked handle invalidates integration |
| Selection requires a verified success and is absorbing | Race selection transactions; reject failed/ambiguous/unselected/mismatched snapshot, duplicate session selection, and state reopening | Kill around selection commit and verify old state/manual review; complete one explicit selection and verify no reallocation | Selection must never be inferred or repeated |
| Session close is absorbing and does not hide unresolved claims | Close with clean terminals; reject unresolved claims without recovery; crash before/after close; reject reopen/allocation | Review close evidence and try restart/reallocation as Trading | Closing over uncertainty without explicit evidence is invalid |
| Manual recovery is explicit and non-authoritative for provider calls | Validate action, predecessor, target digests, epoch, policy, and operator evidence; classify a reservation left committed without a known process after a crash; reject claim/reservation creation or deletion, provider calls, falsified `NOT_STARTED`, and recovery from closed success | Administrator signs/records each reservation classification and recovery action; Trading cannot author recovery or alter history | Recovery must explain uncertainty, never erase it or reopen a consumed reservation |
| PERSIST, synchronous, foreign keys, one-database scope, lock waits, and integrity checks are fixed | Assert `PERSIST`, `FULL`, foreign keys, no `ATTACH`, no `VACUUM`, no runtime DDL/automatic migration, bounded pre-claim `BEGIN IMMEDIATE` waits, local-file assumptions, `quick_check`, `foreign_key_check`, and full integrity-check results | Inspect SQLite pragmas and file locks on Windows; hold locks and corrupt a copy only, not the live authority | Unsupported durability, extra database attachment, or corruption must fail closed |
| PERSIST journal lifecycle is compatible with the exact ACL | Provision the main database and persistent rollback journal in advance; assert normal transactions never require journal recreation, deletion, rename, or arbitrary directory creation; fail the test if those rights are requested | Run under the exact Trading DACL, interrupt transactions, inspect journal persistence, and verify the authority refuses rather than weakening directory permissions when the build needs recreation | PERSIST failure under the approved ACL is a Milestone B blocker; broker service is the fallback architecture decision |
| Database and persistent-journal backups are consistent and signed | Validate SQLite online-backup API output or a fully quiesced reviewed main-database/journal copy; reject main-file-only or active-journal copies; validate backup manifest, DB digest, bootstrap digest/signature, schema, and release digest | Administrator performs online and quiesced file-level backup drills; Trading cannot read backup | An inconsistent or unsigned backup is not recoverable authority |
| Rollback cases visible through independently retained signed/bootstrap state fail closed | In isolated copies, test an older-generation database, altered bootstrap or signature, mismatched database/bootstrap digest, copied or cloned root, path alias, and old-epoch executable restart; assert refusal before mutation, process creation, credentials, or provider access. Do not require detection of an internally consistent same-generation database/persistent-journal replacement; record that the database cannot prove its own freshness without independent trusted state | Administrator validates each detectable mismatch and confirms the old-epoch executable path is blocked. A same-generation replacement by Administrator/SYSTEM or trusted-token code is recorded as outside the threat model, not as a passing detection test | Accepting a detectable mismatch or reusing an old epoch is a NO-GO; inability to detect the explicitly out-of-boundary same-generation replacement is not a failure of this milestone |
| Corruption and unavailable material fail closed | Remove/lock/corrupt DB, persistent journal, bootstrap, signature, output root, or backup; assert no new DB, journal deletion/recreation, repair, process, SID, credential, provider, or transport | Stop/rename only test copies, interrupt access, and observe stable refusal and preserved forensic files | Unavailability must never cause fallback or claim inference |
| Schema-1/2 JSON remains historical-only | Parse/verify existing schema-1/2 fixtures and legacy-success diagnostics; assert no row or executable claim is imported | Point a validation-only tool at legacy roots and then run the authority; verify SQLite remains independent | Legacy artifacts must not authorize a call |
| File-based claim authority is not a fallback | Remove SQLite authority or inject valid legacy claim files; assert the capture refuses rather than scanning/repairing/selecting files | Run with old capture root available and SQLite unavailable | Any fallback resurrects the retired authority model |
| Every approved restore is historical-only and creates a new executable epoch | Restore a database containing claims and ambiguity facts; validate and preserve those rows as historical evidence, rotate the signed bootstrap generation, create a new `authority_epoch_id`, and create a newly provisioned empty executable database; assert no old allocation or claim is imported or executablely reused | Administrator performs the restore drill and verifies executable startup is blocked under the old epoch and permitted only after new-bootstrap/new-database provisioning; old restored claims remain historical-only | Any same-epoch executable restore, old-allocation/claim import or reuse, or claim-loss inference is a NO-GO |
| Milestone gates and unattended NO-GO conditions are enforced | Gate evaluation tests require all A-D evidence and separately approved E prerequisites; missing any one blocks unattended mode | Review hardened launch-guard DACL, official XNYS-hours authority, trusted time/process evidence, monitoring/notification, backup/restore, scheduler config, and account rights | A passing manual capture cannot approve unattended scheduling |

## Crash-injection matrix

The authority implementation must expose test-only barriers around these
boundaries without adding production bypasses:

1. before and after session commit;
2. before and after allocation/ordinal commit;
3. before and after permanent request-bound claim commit;
4. immediately before and after launch-reservation `BEGIN IMMEDIATE`;
5. immediately before and after launch-reservation commit;
6. after reservation commit and immediately before `CreateProcessW`;
7. immediately before and after `CreateProcessW(CREATE_SUSPENDED)`;
8. after process-creation failure while recording the failure against the
   existing reservation;
9. before and after Job assignment/verification;
10. before and after process-creation/resume-authorization evidence commit;
11. immediately before and after `ResumeThread`;
12. before and after post-resume ambiguity commit;
13. before and after terminal commit;
14. before and after selection commit; and
15. before and after close or manual-recovery commit.

For each injection, restart verification must classify the database without
directory scans, preserve all committed facts, prevent a second claim/provider
call, and produce a stable sanitized outcome. In particular, a crash after
reservation commit but before process creation leaves the claim and reservation
permanently consumed and requires manual classification; it never authorizes
an automatic second reservation, process, launch attempt, or provider call. A
known process-creation failure is recorded against that reservation and also
cannot authorize a second launch. The expected result after a possible resume
is ambiguity even if no child result is present.

## Concurrency and duplicate-claim matrix

The focused suite launches at least two independent authority clients against
one session, allocation, and committed claim, with barriers at `BEGIN
IMMEDIATE`, ordinal consumption, claim insertion, launch-reservation
insertion/commit, process creation, and terminal/selection transitions. It
verifies that:

- only one allocation can consume each ordinal;
- only one `provider_call_claims` row can reference an allocation;
- exactly one `launch_reservations` row can reference a claim;
- exactly one runner can commit that reservation;
- the losing runner never calls `CreateProcessW(CREATE_SUSPENDED)`;
- a loser receives a deterministic conflict or busy result and cannot call a
  provider;
- a committed claim remains after the winner exits unexpectedly; and
- a crash after reservation commit, a crash before process creation, or a
  process-creation failure never permits an automatic second reservation,
  process, launch attempt, or provider call; and
- concurrent selection and close operations serialize according to the
  transition rules without state regression.

The test repeats with different working directories, path spellings, process
IDs, and environment values to prove they do not create another identity.

## Backup, restore, and rollback matrix

The administrator validation creates an SQLite online backup or fully
quiesced reviewed backup, validates it in staging, runs all integrity,
generation, epoch, and digest checks, and only then exercises the epoch-reset
restore procedure. It separately tests:

- active persistent journal during a raw-copy attempt;
- journal recreation or arbitrary directory-create requirements under the
  exact Trading ACL;
- older bootstrap generation;
- altered bootstrap/signature;
- attempted same-epoch executable restart after restore;
- copied/cloned root on another path or volume;
- path aliases and database/bootstrap digest mismatch;
- database corruption with a valid prior backup; and
- corruption with no valid backup, which must require a new epoch.

It does not claim that a complete replacement of the database and persistent
journal by an internally consistent same-generation pair is detectable from
the database itself. That case is recorded as outside the stated trust
boundary unless independently retained signed/bootstrap state supplies a
mismatch.

The evidence preserves every claim, terminal, and ambiguity fact in the
restored database as historical evidence. It then verifies signed bootstrap
generation rotation, a new `authority_epoch_id`, and a new empty executable
database. No old allocation or claim may authorize a call in the new epoch,
and uncertainty is never converted into proof that a claim did not occur.

## Manual Windows acceptance runbook

The final manual run is performed only after A-C focused tests pass:

1. Administrator verifies the signed bootstrap, owner/DACL, final paths,
   reparse status, local NTFS volume, database/persistent-journal health, and
   recent backup.
2. The Trading account starts exactly one manually invoked capture using no
   credential values in its configuration or environment.
3. The reviewer verifies the claim commit, exactly one committed launch
   reservation, the reservation winner, child SID, Credential Manager read
   boundary, suspended process/Job evidence, one-call fence, result digest,
   cleanup evidence, and terminal state. A two-runner drill verifies that the
   loser never calls `CreateProcessW`.
4. The reviewer repeats with forced termination after resume and confirms
   ambiguity, no retry, no claim deletion, and manual recovery requirement.
5. The administrator restores a test backup as historical evidence, checks
   generation/epoch-reset behavior, preserves the old claims, and provisions a
   new empty executable authority without modifying the old evidence.
6. The operator signs the manual-only result. No scheduler is installed or
   enabled.

Unattended scheduling remains NO-GO unless the later operational milestone
separately approves all of: hardened launch-guard DACL, official XNYS-hours
authority, trusted time/process evidence, monitoring and notification, backup
and restore, and scheduler configuration and account rights.

## Planned verification commands

These are future commands for the implementation milestone, not commands run
for this architecture-only change. They must be adapted to the final test
paths and must not access real credentials or a real brokerage unless a
separate manual approval exists.

```text
.venv\Scripts\python.exe -m pytest -q <focused transactional-authority tests>
.venv\Scripts\python.exe -m pytest -q <focused Windows process/ACL tests>
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
```
