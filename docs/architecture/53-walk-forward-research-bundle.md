# Portable walk-forward research bundles

## Boundary

The portable research-bundle workflow copies one already valid schema-1
walk-forward research session into a fixed directory layout. It loads the
retained manifest through the strict loader and requires a complete successful
offline verification before copying. It does not invoke a provider, trading
workflow, runner, analyzer, comparator, report builder, artifact serializer, or
manifest builder from domain results.

Primary artifacts remain opaque byte streams. The workflow does not parse,
reinterpret, repair, or regenerate JSON or CSV artifacts. It serializes only an
immutable relocated manifest using the existing compact manifest serializer.

## Layout and relocation

The exact caller-provided destination is the bundle root:

```text
manifest.json
artifacts/<position>-<kind-specific-suffix>
```

Filename position is one-based retained artifact position and is separate from
the manifest's existing ordinal contract. The suffixes are
`walk-forward.json`, `walk-forward.csv`, `aggregate.json`, `aggregate.csv`,
`stability.json`, and `stability.csv`. Only retained kinds are copied. Original
filenames are ignored and omitted formats are not inferred.

Pure relocation performs no filesystem access. It constructs new immutable
artifact records that differ only in `path`, then reconstructs the immutable
manifest with every other field unchanged. Exact and case-insensitive generated
path collisions fail. Because paths are excluded from schema-1 UUID5 material,
the relocated manifest must retain the exact source manifest ID.

## Verification and copying

The source manifest is strictly loaded, the destination is planned and
preflighted, and every source artifact is verified before staging exists. The
destination parent must already be a non-symlink, non-reparse real directory.
Existing destination and deterministic sibling staging entries are rejected,
including dangling symlinks and detectable reparse points.

After verification, each source artifact is reopened and revalidated using the
same component `lstat`, final-entry `lstat`, handle `fstat`, regular-file,
symlink, reparse, entry-identity, and before/after mutation rules as offline
verification. Bytes are read once in fixed 64 KiB chunks and written to an
exclusively created regular file while exact length and SHA-256 are computed.
Length, hash, or detectable source mutation failure aborts the operation.

Copied files and the compact relocated manifest are flushed and `fsync`ed.
Directories are `fsync`ed where the platform supports directory handles. The
complete staged manifest is strictly reloaded and must equal the relocated
model, retain the source identity, and pass complete offline artifact
verification before finalization.

## Staging, finalization, and metadata

Staging uses the deterministic sibling
`.<destination-name>.staging`. Staging and final destination consequently share
a volume even when source artifacts reside on another volume. The final
destination is rechecked immediately before sibling-directory rename.

There is no overwrite, replacement, merge, retry, or rollback mode. A
pre-existing staging entry is never deleted. This invocation cleans only a
staging tree it created. Cleanup failure retains and reports the primary failure
as well as the cleanup failure. No fallible operation after a successful rename
changes the result to failure.

The copy does not preserve source timestamps, ownership, ACLs, permissions,
extended attributes, alternate streams, sparse representation, or other
filesystem metadata. It uses no filesystem copy helper, hard link, reflink, or
symlink. Bundle determinism covers relative paths and exact file bytes, not
filesystem metadata.

Directory `fsync` is unavailable through portable Python APIs on Windows and may
be unsupported by other filesystems. The final parent is flushed where
supported before rename and attempted best-effort after rename. This narrows
durability exposure but does not claim universal crash durability or portable
atomic no-clobber behavior.

## Deferred work

Version one creates no archive, README, checksum file, signature, encryption,
compression, registry entry, upload, publication, network operation, database
record, Git operation, or background process. Verification proves equality to
manifest-retained SHA-256 and byte length, not authorship or authenticity.

Archive creation is a separate downstream operation over an already completed
and verified bundle. It never recreates or modifies the bundle. See
`docs/architecture/54-walk-forward-research-archive.md`.
