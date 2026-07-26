# Offline walk-forward research-session manifest verification

## Command and boundary

The dedicated read-only command is:

```text
python -m scripts.verify_walk_forward_research_session_manifest \
  --manifest PATH [--quiet]
```

It reads one existing schema-1 research-session manifest, reconstructs the
existing immutable manifest model, validates its retained structure and
identity, and verifies the exact bytes of every referenced artifact. It never
invokes the manifest builder or serializer. It also never invokes a provider,
runner, analyzer, comparator, report builder, financial workflow, network,
subprocess, Git operation, repair operation, or write behavior.

Referenced walk-forward, aggregate, and stability artifacts are opaque byte
streams. Their JSON or CSV contents are never parsed or reinterpreted.

## Strict manifest reconstruction

The manifest is limited to 4 MiB before UTF-8 decoding. UTF-8 decoding is
strict, and a UTF-8 BOM is explicitly rejected. JSON parsing rejects duplicate
object keys, nonstandard constants, syntax errors, and trailing input.

Every schema object has an exact field set. Missing and unknown fields fail.
Types are exact: booleans are not integers, strings are not coerced, UUID text
must be canonical lowercase text, enum values are exact, and only manifest
schema version 1 is supported. Artifact ordinals retain the existing one-based,
contiguous convention.

Parsing constructs `MetadataEntry`, `ResearchSessionArtifactRecord`, and
`WalkForwardResearchSessionManifest` values directly. It does not call the
builder because the builder accepts destinations and completed artifact bytes.
The immutable manifest constructor remains authoritative for canonical artifact
order, result-family consistency, producer protocol, and UUID5 identity
reconciliation. Duplicate retained artifact paths are additionally rejected by
the parser without broadening the existing manifest model.

Structural reconstruction performs no referenced-artifact filesystem access.

## Filesystem verification

Each retained POSIX path resolves only from the normalized manifest parent.
There is no lookup of alternate locations, extension inference, moved-file
search, or omitted-format inference.

Artifacts are processed in retained manifest order. Detectable symlinks and
Windows reparse points in intermediate components are rejected. The final entry
is inspected with `lstat` and must be a non-symlink, non-reparse regular file.
After opening in binary read-only mode, `fstat` confirms that the handle is a
regular file and still identifies the inspected entry.

Each file is streamed in fixed 64 KiB chunks. Exact integer byte counts and a
SHA-256 digest are computed over every byte. Before/after handle metadata
detects basic concurrent mutation; detected mutation fails as unexpected I/O.
This narrows race exposure but does not claim universally atomic path
containment or mutation detection across platforms.

The immutable per-artifact statuses are:

1. `MISSING_OR_NONREGULAR`
2. `UNEXPECTED_IO`
3. `BYTE_LENGTH_MISMATCH`
4. `SHA256_MISMATCH`
5. `PASS`

Every artifact is inspected. If several fail, the command returns the exit code
of the earliest failed artifact in retained order.

## Terminal behavior and exit codes

Successful non-quiet output is a deterministic human-readable report containing
the manifest identity and ordered artifact evidence. `--quiet` suppresses all
successful output. Failures always print a deterministic report or diagnostic
to standard error, including in quiet mode.

Retained paths and the optional user-authored session label are JSON-quoted.
Expected diagnostics contain no OS exception text, timestamps, elapsed time,
locale-sensitive formatting, or tracebacks.

Exit codes are:

- `0`: all artifacts passed
- `2`: command usage
- `3`: manifest read, size, BOM, UTF-8, or JSON failure
- `4`: manifest schema, structure, protocol, or identity failure
- `5`: missing, symlink/reparse, or nonregular artifact
- `6`: exact byte-length mismatch
- `7`: SHA-256 mismatch
- `8`: unexpected artifact filesystem or I/O failure

There are no retries and no files are modified.

## Security meaning

Verification proves equality to the lengths and SHA-256 hashes retained by the
manifest. It does not establish authorship or authenticity. A separately
designed signing or trust system would be required for that purpose.
