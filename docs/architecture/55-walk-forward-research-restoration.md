# Canonical archive-to-bundle restoration

## Boundary

Restoration consumes one existing canonical uncompressed USTAR walk-forward
research-bundle archive and recreates its completed fixed-layout bundle. It
never invokes a trading workflow, provider, runner, analyzer, comparator,
report builder, primary-artifact serializer, manifest builder, bundle creator,
network operation, subprocess, database, Git operation, or background process.

Only exact embedded bytes are restored. Primary JSON and CSV artifacts remain
opaque. The embedded manifest is copied byte-for-byte and is never reserialized.

## Shared streaming verification

The archive verifier and restorer use the same public canonical streaming
reader. The reader retains the existing canonical USTAR contract, 4 MiB
embedded-manifest limit, safe archive opening, header reconstruction, strict
path rules, exact ordering, payload hashing, zero-padding checks, terminators,
outer SHA-256, and byte-length classifications.

The public reader validates each header, path, order position, and expected
length before exposing payload chunks of at most 64 KiB to an optional
consumer. It parses and validates `manifest.json` before exposing an artifact
entry. It never extracts arbitrary paths or loads artifact payloads into
memory.

Restoration uses two archive passes. The first performs complete verification
without staging. The second reopens the archive through the same public reader,
writes validated payload chunks, and requires the exact manifest model, outer
SHA-256, byte length, and ordered entry evidence from the first pass. This
detects basic mutation between verification and restoration and fails closed.

## Layout and exact bytes

The caller-provided destination is the final bundle root:

```text
manifest.json
artifacts/<position>-<kind-specific-suffix>
```

The embedded manifest must equal the existing pure fixed-layout relocation
model and retain its exact manifest ID. Archive paths must match
`manifest.json`, followed by every retained manifest artifact path in order.
No archive-root directory, additional file, omitted format, README, checksum,
or metadata file is restored.

The second-pass manifest payload is written first and strictly parsed from
those same retained bytes. It must reconcile with the first pass before any
artifact file is created. Output files use exclusive creation. Each payload is
streamed directly from the archive while its exact byte count and SHA-256 are
reconciled. Files are flushed and `fsync`ed.

## Staging and finalization

The destination parent must already be a non-symlink, non-reparse real
directory. The final destination and deterministic sibling
`.<destination-name>.staging` entry must both be absent. Any existing entry,
including a dangling symlink or detectable reparse point, is rejected and
never removed.

Staging begins only after complete first-pass archive verification, fixed-layout
reconciliation, and destination preflight. Restoration creates only the
staging root, `artifacts/`, `manifest.json`, and referenced artifact files.
Staging directories are flushed where supported.

Before finalization, the staged manifest is loaded through the strict loader,
the exact staged layout is checked, and the existing offline manifest verifier
must return complete PASS evidence. The staged manifest model and manifest ID
must equal the embedded values. Final destination absence and staging identity
are rechecked immediately before one sibling-directory rename.

There is no overwrite, replacement, merge, repair, resume, retry, or fallback.
The invocation tracks its staging directory identity and cleans only staging it
created. Cleanup failure preserves both the primary failure and cleanup
diagnostic. No fallible operation after successful rename can change success
into failure.

Directory `fsync` is unavailable through portable Python APIs on Windows and
may be unsupported by other filesystems. Post-rename parent flushing is best
effort. The workflow therefore does not claim universal crash durability,
atomic no-clobber behavior against concurrent creators, authenticity, or
protection from a hostile filesystem actor.
