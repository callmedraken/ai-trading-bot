# Windows production transactional authority service

## Scope and decision

Milestone C2 extracts the reviewed transactional service from the executable
Architecture-77 behavioral harness into
`trading_bot.runtime.windows_transactional_authority`.

C2 preserves Architecture 77 semantics; it does not redefine the relational
model, canonical material, state transitions, evidence contracts, recovery
classifier, or lifecycle lock ordering. Architecture 79 remains the exact
production schema and Architecture 80 remains the executable-authority gate.
Production is still NO-GO.

The extracted service is a durable authority state-machine owner for a
long-only, manually guarded capture. It is not a provider, child-process,
scheduler, credential, or brokerage implementation.

## Trust boundary and entry requirement

The production constructor is:

```python
WindowsTransactionalAuthority(authority: ValidatedProductionAuthority)
```

It immediately calls the public
`require_validated_production_authority(...)` boundary. A test-issued
capability, `InstalledAuthorityValidation`, `ProductionAuthorityEvidence`,
bootstrap evidence, public capability fields, a database path, or a caller
connection is not a production substitute. Production authority cannot be
reconstructed from public fields.

`WindowsTransactionalAuthority.for_test(...)` is the explicitly named
anonymous-memory service seam for a `DisposableAuthorityDatabaseForTest`
produced by the reviewed test-only opener, test lifecycle arbiters, and fake
adapters. It does not accept an arbitrary SQLite connection, a database path,
or a production-authority argument. The opener always opens `:memory:`, then
proves from SQLite's `PRAGMA database_list` that the connection has exactly
one `main` database with an empty filename. File-backed databases, URI
databases, and attached databases are rejected before the test service can use
them. This service exposes only the explicit named state-machine operations;
`invoke_for_test` does not exist.

Architecture-77 file-backed multiprocessing tests use a separate
`Architecture77HarnessAuthority` under `tests/`. That factory creates and
owns one explicit lifecycle containing its fresh temporary root, database,
descriptor, parent bindings, and process-local service token. Parent observer
connections are explicitly bound to that lifecycle; the token is never derived
from a pathname, deterministic identifier, connection identity, or persisted
state. A spawned child receives the factory descriptor as ordinary test
configuration, reopens and validates the database through the descriptor, and
creates a fresh process-local lifecycle and token. Descriptor equality therefore
does not imply shared provenance. The harness checks root placement, one main
database with no attachments, fixed production-path exclusion, schema identity,
and descriptor/database agreement before the supported runtime issuer returns
an exact, sealed, process-local harness core binding. The binding carries the
exact reviewed connection, lifecycle provenance, and reviewed arbiter
configuration to the supported shared `TransactionalAuthorityCore`
implementation API. `from_harness_binding()` accepts only that exact concrete
binding; public subclasses, fakes, serialized values, and caller-defined
binding methods are not accepted. The core accepts a validated binding, not an
arbitrary connection plus caller arbiter; no `for_harness(connection, ...)`
construction route exists. The binding is not executable production
authority. The harness is test correctness/isolation infrastructure, not test
protection against a hostile same-user filesystem process and not production
executable authority. It never passes its path, connection, descriptor, token,
or capabilities to a production facade. Direct SQL/schema fixtures remain
test-owned raw SQLite infrastructure.

The anonymous service, file-backed harness, and production facade execute the
same `TransactionalAuthorityCore` state-machine implementation. The core is a
supported shared implementation API, but storage binding is mandatory:
production obtains its binding only inside `WindowsTransactionalAuthority`,
and file-backed test storage obtains its binding only from the validated
`Architecture77HarnessAuthority` lifecycle. Production storage remains
selected only by the genuine `ValidatedProductionAuthority` and its fixed
approved VFS/storage binding. Consequently test arbiters,
adapters, test-issued capabilities or receipts, harness paths, and harness
descriptors cannot operate production storage through a production API. The
core is not a proof of production authority and is not broadly re-exported by
package convenience modules.

## Fixed database binding

Production opens only the database path already bound into the validated C1
capability. The approved SQLite build/VFS is loaded from code-owned reviewed
material and must match the capability's build-manifest digest. The caller
cannot select a path, URI, VFS, schema artifact, alternate database, or
connection.

The reviewed SQLite connection contract remains `foreign_keys=ON`,
`journal_mode=PERSIST`, `synchronous=FULL`, and `trusted_schema=OFF` where the
Architecture-79 runtime contract applies. C2 adds no `ATTACH`, `VACUUM`, repair,
automatic migration, alternate schema, or write-capable fallback.

The production surface contains only explicit named service operations. It
accepts no caller connection, caller filesystem path, harness descriptor, or
arbitrary operation callback. Public raw-connection durable mutators and
public raw-connection `*_locked_for_test` writers do not exist. Already-held
arbiter tests use the harness-owned named `TestLifecycleLease` operations.

## Durable state-machine ownership

The service owns the Architecture-77 lifecycle across
`authority_metadata`, `sessions`, `attempts`, `provider_call_claims`,
`launch_reservations`, `launch_executions`, `terminals`,
`session_selections`, `manual_recoveries`, and `schema_migrations`.

It retains the reviewed immutable capture-request snapshot, exact
`capture_request/v2` ten-field contract, UUID5 identities, canonical JSON,
evidence digests, parent-child evidence copying, state guards, ordinal
allocation, terminal/selection behavior, and manual recovery semantics.
Unsupported states and invalid evidence fail closed.

The service owns SQLite transactions. A lifecycle boundary rejects a caller's
active transaction before registry resolution, arbiter acquisition, authority
queries, capability consumption, event emission, or adapter invocation. The
ordering remains:

```text
no caller transaction
  -> acquire lifecycle arbiter
  -> re-resolve durable lineage
  -> BEGIN IMMEDIATE when mutation is needed
  -> commit/end transaction
  -> future external boundary, if reviewed and available
  -> persist typed result/receipt
  -> release arbiter
```

No SQLite write transaction is held across an external call, and the service
never waits for the arbiter while holding SQLite.

## Lifecycle-arbiter ownership

Production lifecycle arbitration uses the reviewed machine-global Windows
mutex boundary from Architecture 77/78: `Global\\AITradingBot-Lifecycle-v1-<digest>`.
The digest is derived from the immutable registry/authority lineage:

```json
{"authority_epoch_id":"<epoch UUID>","label":"lifecycle-arbiter/v1","launch_reservation_id":"<reservation UUID>","machine_authority_id":"<machine UUID>"}
```

There is no `Local\\` fallback, caller-selected name, timeout takeover, lock
stealing, lease, heartbeat, temporary production lock, or process-local lock
as authority. The test factory may use the reviewed disposable harness
adapter, which is deliberately not a production security boundary.

## Process-local capability and provenance model

Provider-construction permits, process intents/results, and resume intents/
results are immutable process-local objects. Private issuer tokens and
registries retain the reviewed provenance checks; visible fields do not select
lineage or arbiter identity. Registry records are checked before consumption,
and one-shot permits are consumed at most once. The objects reject pickling
and serialization. Each anonymous `for_test` service receives a fresh opaque
process-local service token. Each file-backed Architecture-77 harness
lifecycle receives its own fresh token; all explicitly bound parent observer
connections for that lifecycle share it, while separate lifetimes and spawned
processes receive distinct tokens even when they reopen the same pathname. The
token is never derived from deterministic IDs, persisted, serialized, or
caller-selected. Closing a lifecycle closes its owned bindings exactly once,
rejects new bindings and operations with the harness boundary error, and
restricts temporary-root cleanup to the creating lifecycle.

Already-held lifecycle tests use the explicit test-owned `TestLifecycleLease`.
One lease binds exactly one reservation, one harness lifecycle, one arbiter
entry, and one process-local core witness. The supported core has no general
witness factory: the reviewed harness binding is the issuer and acquires the
exact reservation arbiter before returning a witness to `TestLifecycleLease`.
Named while-held operations require that witness and reject reservation,
execution, recovery-target, re-entry, post-exit, and closed-lifecycle
mismatches before durable mutation. The witness is invalidated on exit, is not
serialized, and is not production authority.

Test-issued provider/process/resume capabilities and receipts use distinct
test provenance. Production service consumers reject that provenance before
arbiter acquisition or durable mutation; the explicit `for_test` service
context remains the only harness path that accepts it.

Process death destroys unpersisted capabilities. A restarted process does not
reconstruct a permit from SQLite or public fields; it re-resolves durable
state and follows documented manual recovery.

## Durable intent, receipts, and crash/restart behavior

C2 preserves the durable intent/receipt split because SQLite cannot atomically
prove a future provider or Windows call. Provider-call claims, launch
reservations, process intent, process creation result, `PRE_RESUME_READY`,
resume intent/result, post-resume evidence, terminal, and selection remain
distinct durable steps. Ambiguous external outcomes are never automatically
retried.

Recovery remains derived only from validated durable state. In particular:

- `COMMITTED` maps to `CLASSIFY_LAUNCH_RESERVATION`;
- `PROCESS_INTENT_COMMITTED` maps to `CLASSIFY_PROCESS_OUTCOME_UNKNOWN`; and
- an unreceipted `RESUME_INTENT_COMMITTED` maps to
  `CLASSIFY_RESUME_OUTCOME_UNKNOWN`.

Unknown outcomes remain manual-review states and do not grant retry
permission or fresh capabilities.

## Production versus test adapter boundary

C2 provides the typed adapter protocol only. There is no production provider
client, HTTP call, Credential Manager access, private-key load,
`CreateProcessW`, `ResumeThread`, Job Object operation, child execution,
scheduling, or live-order implementation. Calling a production service
without a future reviewed adapter fails closed; it is never treated as a
successful no-op.

Behavioral tests retain disposable SQLite setup, the file-lock lifecycle
adapter, fake external observations, direct-SQL negative vectors, and
test-only capability factories. In-memory service vectors use the explicit
`for_test` seam. File-backed cross-process vectors use
`Architecture77HarnessAuthority` and its explicit `TestLifecycleLease`; they
do not route a file connection through the anonymous-memory service, a raw
connection cache, an arbitrary callback, or an unconstrained while-held core
writer. The harness imports the supported core API, owns its file bindings,
and reopens only through its descriptor. The harness and production therefore
exercise one state-machine implementation while retaining separate storage
and authority boundaries.

## C2 exclusions and next milestone

C2 does not publish production trust anchors, a production provider adapter,
credentials, Windows process effects, scheduling, unattended execution, or
live trading. It does not change the Architecture-79 SQL resource, schema
version, deterministic identity material, canonical bytes, or evidence
digests.

`snapshot_digest` on a successful terminal is an upstream-verified evidence
input contract. C2 checks its explicit 32-byte shape and persists the supplied
canonical evidence, but it does not verify external provider output or issue a
verified-snapshot capability. C2 has no reviewed production
provider/output-verification implementation; consequently production
successful capture remains unavailable/NO-GO until a future reviewed
effectful boundary establishes verified snapshot evidence. C3 must define how
captured content is verified and how that verified result is authorized and
passed into terminal recording before production enablement. C2 does not
invent that mechanism.

The next milestone must separately review and implement the inert-to-effectful
external boundary: approved provider construction and transport, suspended
child creation and Job Object containment, resume and cleanup evidence,
native Windows acceptance, and the associated crash/recovery and security
controls. Production remains NO-GO until that milestone and the remaining
Architecture-78/79 acceptance conditions are complete.
