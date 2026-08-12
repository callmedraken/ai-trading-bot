# Windows production-authority capability

## Scope and decision

Milestone C1 consolidates the reviewed Windows-to-SQLite validation chain into
one supported production interpretation of executable authority:
`ValidatedProductionAuthority`.

The capability means exactly that the fixed installed Windows authority has
passed the complete validation chain and is `INITIALIZED_SUPPORTED`. It is
process-local provenance, immutable, secret-free, and not a serialized
authority. It does not enable provider execution, child launch, scheduling,
credentials, or live orders. Production remains NO-GO until the approved
production trust anchors, release material, and SQLite build/VFS material are
published.

## Trust boundary

The boundary is deliberately one-way:

```text
raw fixed machine state
        |
        v
Windows path/handle/security validation
        |
        v
signed bootstrap validation
        |
        v
approved release + SQLite build/VFS
        |
        v
VFS-bound read-only database validation
        |
        v
exact schema/metadata/migration validation
        |
        v
21 persisted evidence-pair digests
        |
        v
bootstrap/database/release/build reconciliation
        |
        v
ValidatedProductionAuthority
```

Raw paths, handles, SQLite connections, bootstrap bytes, manifests, and
individual evidence objects are untrusted inputs or disposable validation
inputs. Administrator validation facts remain useful for lifecycle reporting,
including `NOT_PRESENT`, `PRECREATED_UNINITIALIZED`,
`INITIALIZED_SUPPORTED`, and unsupported/mismatched states, but they are not
executable authority by themselves.

## Evidence layers

The administrator layer produces `ProvisioningEvidence`,
`BootstrapVerification`, `ProductionAuthorityEvidence`, and the immutable
`InstalledAuthorityValidation` result. The low-level database validator
returns only administrative state and database evidence; it never mints a
capability. The complete installed-authority validator may carry an optional
`ValidatedProductionAuthority`, but only the capability carries executable
authority meaning.

Disposable tests may use the explicitly named `*_for_test` validation and
capability-injection entry points. Those paths may use test registries,
temporary database paths, caller-owned connections, and reviewed test
manifests where the existing test contract requires them. Production entry
points never delegate trust selection to those functions.

## Capability issuance

The one obvious production issuer is
`acquire_validated_production_authority()`. It is parameterless and uses the
code-owned fixed authority tree, `PRODUCTION_PINNED_BOOTSTRAP_KEYS`, approved
release material, and approved SQLite build/VFS material. It fails closed when
any approved resource is absent or when any validation step fails.

Issuance requires all of the following:

1. fixed Windows parent, root, object, owner, DACL, final-path, reparse, and
   lifecycle-mutex checks;
2. the signed bootstrap and resolved Trading SID to agree;
3. an approved release manifest and approved SQLite build/VFS identity;
4. one fixed VFS-bound read-only database with its persistent journal;
5. exact SQLite integrity, build, trusted-schema, and materialized-schema
   validation;
6. exact immutable metadata and migration reconciliation to the bootstrap and
   approved release;
7. every one of the 21 persisted evidence-byte/digest pairs to be valid; and
8. `database_state == INITIALIZED_SUPPORTED`, with complete
   `ProductionAuthorityEvidence` present and all bootstrap, database, release,
   and SQLite-build identities reconciled.

The capability exposes only sanitized immutable identity facts already proved
by that chain: authority and machine IDs, bootstrap generation and digest,
approved SID, provider and operation policy, database identity/path, schema
identity, metadata/migration identity, and release/build digests. It contains
no secrets, credentials, handles, connections, private keys, mutable
collections, or raw provider data. C1 does not invent a new deterministic
identity.

## Provenance and consumption

The capability constructor is issuer-token gated by separate private
process-local production and test markers owned by the validation module. The
marker is stored in a private non-serialized slot, and public fields are not a
supported reconstruction mechanism. Production consumers require the exact
production marker, so a test capability with identical public fields remains
unacceptable. The object rejects mutation, serialization, and pickling. This
is supported-API provenance fencing, not a claim that Python can defend
against malicious reflective code that already controls the trusted process.

C1 does not impose one-shot consumption because it performs no external
effect. Future provider, `CreateProcessW`, and `ResumeThread` permits remain
separate one-shot Architecture-77 capabilities. Future production authority
services must accept this capability (or a reviewed runtime-session derivative)
instead of raw paths, arbitrary connections, caller-selected manifests, or
partially validated evidence.

The production initializer now consumes the capability for both idempotent
success and post-commit success. Provisioning uses the same centralized
complete-validation boundary for an already initialized supported database,
while its external CLI result remains the existing stable, secret-free
`ProvisioningEvidence` contract.

## Next milestone

C2 extracts the reviewed Architecture-77 transactional service into the
production runtime and makes it require `ValidatedProductionAuthority` (or
its future runtime-session derivative).

C1 itself does not claim that provider or process execution is enabled.
