# Canonical walk-forward research-bundle archives

## Boundary and format

The archive workflow consumes one already completed portable research bundle.
It strictly loads the retained manifest, requires the fixed bundle layout, and
uses the existing offline manifest verifier before archive staging. It never
creates a bundle, regenerates a manifest, serializes a primary artifact, or
invokes a provider, runner, analyzer, comparator, report builder, financial
workflow, network, subprocess, database, Git operation, or background process.

Version one uses one project-owned canonical uncompressed POSIX USTAR format.
ZIP is not used because its local and central headers, DOS timestamps, platform
attributes, encoding flags, extra fields, and optional data descriptors create
a larger reproducibility surface. The production writer does not use
`tarfile` output as its contract.

## Entries and canonical headers

The archive contains bundle contents rather than the source root directory.
Entry order is `manifest.json`, then referenced artifacts in retained manifest
order. No directory entry is emitted.

Entry names are strict ASCII normalized relative POSIX paths using `/`. Empty,
absolute, dot, parent, backslash, Unicode, duplicate, case-fold-colliding, and
over-100-byte names fail. Current fixed bundle paths satisfy this boundary.

Every 512-byte header uses mode `0644`, UID and GID zero, mtime zero, regular
type `0`, empty link and ownership names, `ustar\0` magic, `00` version, zero
device numbers, empty prefix, and zero header padding. Numeric fields use one
zero-padded ASCII octal representation terminated by NUL. The checksum is six
octal digits, NUL, and space, computed while treating the checksum field as
eight spaces.

Payloads retain exact bundle bytes and receive only the zero bytes needed to
reach the next 512-byte boundary. The archive ends with exactly two zero
blocks. It has no 10 KiB record padding, compression, PAX record, GNU
extension, sparse representation, signature, checksum sidecar, README, or
ownership metadata.

## Creation and verification

Before staging, creation requires the exact bundle filesystem layout, complete
offline artifact verification, exact manifest-byte reconstruction, safe entry
names, supported sizes, canonical headers, an accepted destination directory,
and absent final and staging entries.

Each source entry is reopened during writing. `lstat`, `fstat`, regular-file,
symlink/reparse, entry identity, and before/after metadata checks narrow race
exposure. Artifacts are streamed in fixed 64 KiB chunks. Headers use manifest
byte lengths rather than mutable stat sizes. Exact entry length and SHA-256 are
reconciled while the whole archive SHA-256 and byte length cover headers,
payloads, padding, and terminators.

The staged file is flushed and `fsync`ed, then passed to the public streaming
archive verifier with expected outer evidence. The verifier reads one header at
a time and retains only the embedded manifest, which remains subject to the
existing 4 MiB limit. It reconstructs every canonical header byte, verifies
manifest structure and identity, streams each artifact hash and length, requires
zero padding, and requires exactly two terminators followed by EOF. It never
extracts.

Directories, links, devices, FIFOs, sparse entries, extensions, compression,
duplicate or reordered entries, concatenated archives, and trailing bytes all
fail.

## Identity, staging, and durability

The final filename is:

```text
walk-forward-research-bundle-<manifest-id>.tar
```

The filename does not establish manifest identity; identity comes only from the
strictly parsed embedded manifest. Archive evidence is exact SHA-256 and byte
length. No archive UUID is defined, and archive evidence does not change bundle
or manifest identities.

Staging uses a deterministic sibling file named `.<filename>.staging`.
Existing final or staging entries are rejected and never overwritten. The
invocation cleans only staging it created and preserves the primary failure if
cleanup also fails. Final destination absence is rechecked immediately before
rename.

Files and destination directories are `fsync`ed where supported. Directory
`fsync` is unavailable through portable Python APIs on Windows and may be
unsupported elsewhere. Post-rename parent flushing is best effort and cannot
turn a successful rename into failure. These measures do not claim universal
crash durability or atomic no-clobber behavior against concurrent creators.
