# Windows production-authority capability

## Scope and decision

Milestone C1 defines two distinct proof planes. Administrator installation
conformance produces administrative evidence. The dedicated standard Trading
process performs a separate fixed-trust, read-only executable-authority proof
and, only after that proof succeeds, receives `ValidatedProductionAuthority`.

`InstalledAuthorityValidation` is administrator installation/conformance
evidence. It is not executable authority and never issues or carries a
`ValidatedProductionAuthority`.

`ValidatedProductionAuthority` is process-local, immutable, secret-free
Trading-runtime provenance. It means that the exact consuming Trading process
has passed the reviewed runtime-visible Windows and SQLite authority proof and
may enter the future reviewed production transactional service. It does not
enable provider execution, child launch, scheduling, credentials, or live
orders. Production remains NO-GO until the approved production trust anchors,
release material, SQLite build/VFS material, and native Windows acceptance are
published.

## Corrected trust boundary

The proof planes are intentionally separate:

```text
Elevated administrator process
        |
        v
Complete Architecture-78/79 installation conformance
        |
        v
InstalledAuthorityValidation
(administrative evidence only)
        |
        +--> parent and backup administrator/SYSTEM protection become
             environmental trust preconditions for the Trading runtime

Dedicated standard Trading process
        |
        v
Exact current-token proof
        |
        v
Direct runtime-visible fixed-object validation
(no parent-chain validation and no backup inspection)
        |
        v
Signed bootstrap, approved release/build, and read-only VFS SQLite proof
        |
        v
Exact schema, metadata, migration, 21 evidence pairs, and reconciliation
        |
        v
ValidatedProductionAuthority
        |
        v
Future Architecture-77 reviewed production service
```

Raw paths, handles, SQLite connections, bootstrap bytes, manifests, and
individual evidence objects remain untrusted or disposable validation inputs.

## Administrator versus Trading runtime

| Concern | Administrator installation conformance | Trading runtime authority acquisition |
| --- | --- | --- |
| Caller | Elevated administrator | The exact dedicated standard `Trading` process |
| Entry point | `validate_installed_authority_complete()` and administrator initialization/provisioning boundaries | Parameterless `acquire_validated_production_authority()` |
| Windows objects | Complete fixed tree, including parent and `backup\` | Root, bootstrap, signature, database, journal, and capture-output only |
| SQLite proof | Complete read-only installed proof and administrative state classification | Complete read-only executable proof and `INITIALIZED_SUPPORTED` requirement |
| Mutation | Validation is read-only; initialization/provisioning retain their reviewed administrator mutations | No writes, repair, schema mutation, migration, journal cleanup, mutex creation, or mutex acquisition |
| Result | `InstalledAuthorityValidation` and its administrative evidence | `ValidatedProductionAuthority` with production provenance |

## Administrator installation conformance

The elevated administrator boundary continues to prove the complete
Architecture-78/79 chain:

1. fixed parent, root, bootstrap, signature, database, journal, capture-output,
   and `backup\`;
2. exact final paths, expected object types, no reparse substitution, local
   NTFS volume, owner, protected DACL, ACE flags, and ACE masks;
3. lifecycle-mutex security policy;
4. signed bootstrap and the resolved local Trading account;
5. approved release and SQLite build/VFS material;
6. one fixed VFS-bound read-only SQLite connection;
7. exact schema, metadata, migration, and all 21 persisted evidence pairs;
8. bootstrap/database/release/build reconciliation; and
9. exact database-state classification, including `NOT_PRESENT`,
   `PRECREATED_UNINITIALIZED`, and `INITIALIZED_SUPPORTED`.

The result is administrative evidence. A centralized administrator consumer
may require reconciled `INITIALIZED_SUPPORTED` evidence, but that operation
does not issue executable authority.

## Trading runtime authority acquisition

`acquire_validated_production_authority()` is the sole supported production
capability issuer. It is parameterless and uses only fixed paths, pinned
production bootstrap keys, and code-owned approved release/build material.

At the beginning of the path, Win32 token state must prove:

```text
resolve_current_token_sid() == resolve_local_Trading_sid()
current token is not elevated
current token is not an administrator token
```

The reviewed public primitives are the current-token SID resolver,
`require_trading_standard_account()`, `is_current_token_elevated()`, and
`is_current_token_administrator()`. A caller-supplied SID, username string,
environment variable, display name, or command-line value is never a security
input. Another standard user, an administrator, an elevated token, or an
invalid Trading account fails closed.

The runtime path directly opens and inspects only the runtime-visible set:

- `F:\AITradingBot\Authority\`;
- `authority.bootstrap.json`;
- `authority.bootstrap.sig`;
- `authority.sqlite3`;
- `authority.sqlite3-journal`; and
- `capture-output\`.

Each opened object is checked for its exact final path, expected type, no
reparse substitution, local NTFS volume, administrator ownership, and exact
protected DACL/Trading policy. Bootstrap and signature bytes are read from
the already inspected handles. Runtime validation does not call the complete
administrator tree validator, `validate_fixed_parent_chain()`, or any helper
that transitively invokes it. It does not inspect `backup\`.

The lifecycle mutex policy may be checked only through the repository's
non-mutating policy validation. C1 capability issuance does not create or
acquire the mutex; the future service acquires it at its own reviewed
boundary.

## Parent and backup trust precondition

`F:\AITradingBot` and
`F:\AITradingBot\Authority\backup\` are intentionally protected for
administrator/SYSTEM access and intentionally have no Trading ACE. Their
reviewed protection is an environmental trust precondition established by
administrator provisioning and complete administrator validation.

The Trading runtime does not independently revalidate those objects and must
not describe its proof as complete installed validation. Widening either ACL,
adding a privileged broker, IPC, durable attestation, a new signing key, or a
validation account is outside this architecture.

## SQLite and evidence proof

After the fixed runtime-visible Windows proof, the runtime:

1. verifies the signed bootstrap against `PRODUCTION_PINNED_BOOTSTRAP_KEYS`;
2. requires the signed approved account SID to equal the current Trading SID;
3. loads the approved release manifest and SQLite build/VFS from code-owned
   sources;
4. requires the fixed database/journal pair;
5. opens the fixed database through the approved VFS in read-only mode;
6. validates SQLite prerequisites and requires `INITIALIZED_SUPPORTED`;
7. validates exact schema, metadata, migration, and all 21 persisted evidence
   pairs; and
8. reconciles bootstrap, database, release, and SQLite-build identities.

There is no write-capable fallback, schema repair, migration, `ATTACH`,
`VACUUM`, or journal cleanup. Only then is production capability issuance
allowed.

## Capability semantics and provenance

The capability constructor is issuer-token gated by separate private
process-local production and test markers owned by the validation module. The
production marker can be used only by the Trading runtime acquisition path.
The test marker is reachable only through explicitly named `*_for_test`
construction boundaries and cannot mint production provenance.

The capability exposes sanitized immutable identity facts already proved by
the applicable chain: authority and machine IDs, bootstrap generation and
digest, approved SID, provider and operation policy, database identity/path,
schema identity, metadata/migration identity, and release/build digests. It
contains no secrets, credentials, handles, connections, private keys,
mutable collections, or raw provider data. Public fields are not a supported
reconstruction mechanism.

`require_validated_production_authority()` accepts a capability directly. It
requires the exact capability type, production provenance, fixed database
path, exact production schema identity, and valid immutable field shapes. It
does not reconstruct or reinterpret administrator evidence. Test provenance
and administrator evidence are rejected at this executable boundary.

The capability rejects assignment, deletion, serialization, and pickling.

## Administrator initialization

Administrator initialization remains elevated. Its idempotent path is:

```text
complete administrator validation
  -> reconciled INITIALIZED_SUPPORTED administrator evidence
  -> selected release/build continuity
  -> InitializationEvidence
```

Its new-initialization path is:

```text
preflight administrator validation
  -> reviewed initialization transaction
  -> close writable connection
  -> post-commit administrator validation
  -> pre/post machine, epoch, generation, database, SID, and bootstrap continuity
  -> reconciled INITIALIZED_SUPPORTED administrator evidence
  -> selected release/build continuity
  -> InitializationEvidence
```

A release/build change between selection and post-commit validation fails
closed. Initialization does not require executable capability merely to report
administrator success. Provisioning continues to use the administrator
boundary and its existing secret-free evidence contract.

## Test and conformance model

Tests must keep administrator evidence and runtime capability paths distinct.
Production provenance tests exercise the real parameterless runtime issuer
while mocking only lower-level native/resource inputs. Test fixtures use
explicit `*_for_test` APIs and never import private issuer markers or private
issuance helpers.

Required regressions include rejection of administrator/elevated and other
standard-user tokens, acceptance only of the exact current Trading token,
absence of parent/backup calls in runtime acquisition, direct inspection of
all runtime-visible objects, read-only SQLite/evidence reconciliation,
production/test provenance separation, and deletion immutability.

## Production NO-GO conditions and C2

Production remains NO-GO pending the approved production P-256 trust anchor,
administrator provisioning, real Trading ACL acceptance, native SQLite VFS
and locking acceptance, reparse/substitution acceptance, native trust
publication acceptance, and cross-session lifecycle-mutex acceptance.

C2 still requires `ValidatedProductionAuthority` directly at the future
reviewed Architecture-77 transactional-service boundary. C1 does not enable
provider calls, process creation, scheduling, unattended execution, or live
orders.
