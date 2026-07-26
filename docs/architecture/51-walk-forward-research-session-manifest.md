# Walk-forward research-session manifest

## Boundary

The research-session manifest is a CLI/audit envelope for primary artifacts
already rendered by one walk-forward command execution. It is not a financial
domain result. The builder accepts only immutable descriptors containing an
exact normalized destination, artifact kind, serializer-contract schema
version, result UUID, and exact bytes. It accepts no domain result, serializer,
stream, callback, unresolved request, or lazy value.

The command renders each requested primary artifact once. When requested, it
builds and serializes the manifest from those exact UTF-8 bytes before staging.
No provider, runner, analyzer, or serializer is invoked by manifest construction
or verification.

## Contents and identity

Manifest JSON schema 1 records the fixed producer protocol, walk-forward
configuration schema version, result IDs derived from present artifact
descriptors, optional unpadded session label, ordered unique metadata, and an
ordered artifact array. Each artifact record contains its ordinal, kind,
serializer schema version, result ID, manifest-parent-relative POSIX path,
SHA-256 digest, and exact byte length.

Artifact order is walk-forward JSON, walk-forward CSV, aggregate JSON, aggregate
CSV, stability JSON, then stability CSV, omitting destinations not requested.
At least one walk-forward artifact is required. Kinds are unique and each
artifact family has exactly one result ID. Optional families are absent rather
than inferred.

The UUID5 identity binds schema and protocol versions, configuration schema,
derived family IDs, label, ordered metadata, and each artifact's ordinal, kind,
schema, result ID, SHA-256 digest, and byte length. Paths are excluded so a
byte-identical session remains relocatable. Compact and pretty projections have
the same manifest ID.

## Paths, hashing, and verification

All destinations are normalized and collision checked before configuration
parsing. Primary artifacts and the manifest must share a volume so their paths
can be represented relative to the normalized manifest parent with `/`.
SHA-256 is the only version-one algorithm and covers every exact artifact byte,
including final newlines and CSV quoting.

Offline verification reads each referenced regular file as bytes and compares
its exact length and SHA-256 digest. It does not parse JSON or CSV and has no
financial or serialization dependencies. Model validation itself performs no
filesystem access.

## CLI and replacement

The existing walk-forward command adds `--manifest`, `--manifest-pretty`,
`--session-label`, and repeatable `--session-metadata KEY=VALUE`. Manifest
options require `--manifest`; a manifest requires at least one primary output.
Schema 1 rejects an existing manifest even with `--overwrite`.

All primary artifacts and the manifest are staged before replacement. Existing
primary replacement order is preserved and the manifest is replaced last.
Later replacement failure does not roll back earlier replacements. No output
failure retries or reruns financial work or serialization. Version one defines
no CSV manifest, signing, database, registry, network storage, or concurrency.

The separately defined portable research-bundle workflow may rewrite only
retained artifact paths into a fixed directory layout. Since paths are excluded
from manifest identity, strict reconstruction must retain the exact manifest ID.
See `docs/architecture/53-walk-forward-research-bundle.md`.
