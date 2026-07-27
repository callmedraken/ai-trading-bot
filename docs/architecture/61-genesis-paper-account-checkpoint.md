# Genesis paper-account checkpoint

## Scope

Schema 1 converts an explicit caller-authored opening account assertion into an
immutable `GENESIS` paper-account checkpoint. It is a deterministic domain and
serialization boundary. It does not accept broker evidence, historical fills,
orders, lifecycle events, or a clock that was not supplied by the caller.

This milestone does not create successor checkpoints, lineage edges, cycle
execution, full-lineage verification, CLI commands, or filesystem output.

## Retained state

The opening assertion retains UTC `as_of`, nonnegative cash, ordered positions,
exact quantity, exact total cost basis, derived average cost, cumulative
realized profit and loss, and ordered application metadata. Cash-only,
zero-cash invested, and cash-plus-position accounts are supported. An account
with zero cash and no positions is rejected because `PaperLedger` cannot
safely represent it, even when realized profit and loss is nonzero.

The compact-ledger state is reconstructed from these values under the existing
`compact-paper-ledger-arithmetic-v1` policy. Total cost basis is authoritative;
average cost is only the exact derived value. The request rejects nonempty open
orders, duplicate symbols, unsupported scalars, nonfinite Decimal values,
invalid Decimal bounds, and caller metadata using `checkpoint.`, `lineage.`,
or `application.` prefixes.

## Identity

Three dedicated UUID5 namespaces and framed, versioned UTF-8 material derive:

- an account-state identity from retained account values and ordered positions;
- a genesis lineage identity from account state and ordered metadata;
- a checkpoint identity from `GENESIS`, sequence `0`, account-state identity,
  compact-ledger identity, canonical empty-engine fingerprint, lineage
  identity, and ordered metadata.

Artifact SHA-256 and byte length are represented only by
`PaperAccountCheckpointReference`; they do not affect any checkpoint-domain
identity. Output paths, filesystem metadata, diagnostics, random identifiers,
and unsupplied clocks are likewise excluded.

## Canonical artifact and verification

Schema 1 serializes one compact UTF-8 JSON document with sorted object keys,
preserved array ordering, ASCII escaping, exponent-free Decimal strings,
canonical lowercase UUID text, UTC `Z` timestamps, and exactly one final
newline. Artifacts are capped at 1 MiB; positions and metadata are capped at
100 each.

The strict parser rejects BOMs, invalid UTF-8, duplicate/missing/unknown fields,
comments, trailing bytes, floats, nonstandard constants, noncanonical scalar
text, and inconsistent derived identities. Offline verification uses no
provider, broker, network, filesystem output, scheduler, strategy, or clock.
It re-derives every identity, restores the compact ledger, requires exact state,
position order, empty fill membership, and `is_compact_restored`, then requires
byte-for-byte canonical reserialization. Only a complete `PASS` result exposes
the reconstructed checkpoint and ledger.
