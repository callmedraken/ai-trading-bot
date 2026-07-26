# Verified-snapshot paper-cycle canonical report

## Boundary

Schema 1 serializes one complete immutable `VerifiedSnapshotPaperCycleResult`
and verifies it offline against the separately supplied original daily-snapshot
artifact. It adds no execution behavior, command, file output, persistence,
scheduling, provider access, broker integration, strategy, optimizer, or
research-artifact boundary.

The report embeds snapshot identity, hash, length, calendar/session linkage, and
all prepared and runtime evidence, but never embeds the snapshot payload.
Verification may inspect only caller-supplied report bytes, caller-supplied
snapshot bytes, and the identified calendar.

## Canonical schema

The root contains exactly `schema_version` and `result`. The result is an
explicit allowlisted representation of the complete prepared input,
ledger-bootstrap evidence, existing seven-stage paper-runtime result, adapter
status, final public account state, diagnostics, and deterministic identities.
Ordered domain values are arrays. Risk-context mappings are ordered arrays of
key/value records rather than JSON objects.

Canonical JSON is UTF-8 with sorted object keys, compact separators,
`ensure_ascii=True`, no nonstandard constants, and exactly one final newline.
UUID and SHA-256 text is lowercase, timestamps are canonical UTC, dates are ISO
dates, enum values use their public value text, and Decimals are exponent-free
canonical strings. Schema 1 limits reports to 16 MiB, arrays to 20,000 items,
strings to 16,384 characters, Decimal text to 256 characters, and integers to
signed 64-bit magnitude.

Strict parsing rejects BOM, invalid UTF-8, duplicate, missing, or unknown
fields, comments, trailing data, JSON floats, nonstandard constants, invalid
scalar types, noncanonical scalars or bytes, unsupported schema versions, and
retained immutable models whose identities or relationships do not reconcile.
No recursive dataclass conversion is used; schema 1 explicitly freezes every
retained model and field.

## Offline verification

Verification optionally compares the outer report SHA-256 and byte length,
strictly validates the report tree, and verifies the separate snapshot using
the report's exact snapshot hash and byte length. A complete PASS snapshot is
required and its UUID must match.

The verifier reconstructs only the caller-authored preparation request, reruns
the existing pure preparation boundary, and requires exact prepared evidence.
It then invokes the existing one-shot execution adapter exactly once with a
fresh disposable runtime and requires exact runtime stages, fills, state IDs,
final public state, adapter status, result ID, and canonical report bytes.
Ambient clocks and Decimal context do not affect replay.

A verification result is frozen and slotted. Reconstructed result access is
available only on complete `PASS`; every `FAIL` carries stable diagnostic codes
and no partial result. Diagnostics distinguish outer evidence mismatch, report
syntax, strict schema/canonicalization, snapshot linkage, preparation replay,
execution replay, and adapter identity/state reconciliation. Human diagnostic
text is not deterministic identity material.

## Deferred work

Run and verify CLI commands, filesystem staging, durable storage, signatures,
schedulers, retries, crash recovery, broker/provider integration, and any
additional execution policy remain outside this milestone.
