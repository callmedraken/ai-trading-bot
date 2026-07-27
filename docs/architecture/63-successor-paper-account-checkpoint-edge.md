# Successor paper-account checkpoints and one-edge verification

## Scope

Milestone 2D turns exactly one completed checkpointed verified-snapshot paper
cycle into an immutable `CYCLE_SUCCESSOR` checkpoint. It also defines a
canonical checkpointed-cycle report and a strictly offline verifier for one
predecessor-to-successor edge rooted at a genesis checkpoint.

It does not traverse or verify a full lineage, add a CLI or filesystem staging,
schedule work, mutate a prior checkpoint, select a strategy, contact a market
data provider or broker, or permit live trading.

## Report and successor state

The canonical report retains the complete deterministic replay request plus the
identity-bearing cycle evidence: predecessor artifact reference and lineage,
opening and final compact ledger states, cumulative realized profit and loss,
preparation and runtime fingerprints, fills, status, and diagnostic codes. Its
UUID5 binds only its explicit versioned material and cycle-result identity; it
does not bind report bytes, artifact hashes, paths, clocks, diagnostic text, or
mutable objects.

A successor retains sequence `prior + 1`, the final compact state, realized P&L
before and after the cycle, a fresh canonical empty-engine fingerprint, prior
checkpoint artifact reference, application identity, report artifact reference,
snapshot reference, and ordered metadata. Its account-state UUID5 binds the
final compact-state identity and both P&L values. Its lineage UUID5 binds the
prior lineage, prior checkpoint, producing cycle-result, and successor sequence.
Its checkpoint UUID5 binds all checkpoint-domain state and ordered metadata, but
not report/checkpoint artifact bytes or hashes.

## Canonical encoding and bounds

Both new artifacts are strict schema-1 UTF-8 JSON. The parsers reject BOMs,
invalid UTF-8, duplicate/missing/unknown fields, floats, nonstandard constants,
noncanonical UUID, timestamp, Decimal, and SHA-256 text, and any bytes that do
not equal canonical reserialization. Arrays, strings, finite Decimal text,
integers, metadata counts, metadata keys, metadata values, and total artifact
bytes have explicit bounds. Array order, position order, fill order, and
ordered metadata are preserved.

## Offline edge verification

The verifier accepts exact report, predecessor checkpoint, daily snapshot, and
successor checkpoint bytes plus an identified calendar. It validates supplied
successor byte evidence before parsing, verifies the predecessor and snapshot
against retained references, replays the checkpointed cycle exactly once, and
requires exact retained report evidence. It reconstructs the successor from
that replay, requires every retained reference, identity, sequence, lineage,
state, P&L value, and fresh empty-engine fingerprint to agree, then restores
the successor compact ledger and requires empty fills and the compact-restored
marker.

`PASS` exposes only the complete replayed cycle result, successor checkpoint,
and restored ledger. `FAIL` exposes none of them and instead retains stable,
non-identity diagnostic codes. The verifier has no provider, network, broker,
filesystem-output, scheduler, or clock dependency.
