# Authoritative capture-attempt evidence validation

The focused authority suite verifies canonical vectors and round trips for
allocation, history head, schema-2 terminal, zero-call proof, and recovery;
exact READY-decision reconciliation; genesis and immediate ordinal consumption;
pointer-selected chain verification without directory discovery; state and
classification invariants; explicit zero-call evidence requirements; pure
retry-policy outcomes; manual recovery binding; stale compare-and-swap and
crash-left staging behavior; and preservation of the old pointer on failure.

The five CLI entry points are artifact-only wrappers. They are tested with
temporary absolute roots and never retrieve credentials, create children,
call Alpaca, capture snapshots, schedule work, or advance paper lineage.
