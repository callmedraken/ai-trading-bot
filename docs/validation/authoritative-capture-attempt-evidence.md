# Authoritative capture-attempt evidence validation

The focused authority suite verifies canonical vectors and round trips for
allocation, history head, schema-2 terminal, zero-call proof, and recovery;
exact READY-decision reconciliation; genesis and immediate ordinal consumption;
pointer-selected chain verification without directory discovery; state and
classification invariants; explicit zero-call evidence requirements; pure
retry-policy outcomes; manual recovery binding; stale compare-and-swap and
crash-left staging behavior; success-selection identity/digest/linkage
verification; deletion, modification, and cross-attempt replacement rejection;
ambiguous terminal preservation after restart; and preservation of the old
pointer on failure. Canonical schema-1 and schema-2 history-head identity and
byte vectors, legacy unbound-success migration blocking, and separate recovery
selection-policy binding are also verified.
The transition matrix is tested for absorbing success/closed states, exact
terminal-selection source state, impossible predecessor/cause transitions,
allocation rejection after successful or ambiguous terminals, exact recovery
allocation/proof/terminal bindings, action-specific manual recovery evidence,
allocation and terminal publication evidence parity, terminal field and
policy reconciliation, preservation of verified zero-call proof through
closure, and rejection of committed-success recovery from
`RECOVERY_REQUIRED`,
canonical-before-migration legacy validation, direct legacy-success review
versus conflicting legacy successors, and semantically invalid schema-2
success heads. Forged canonical chains never pass disk verification merely
because their individual records have valid identities.

The five CLI entry points are artifact-only wrappers. They are tested with
temporary absolute roots and never retrieve credentials, create children,
call Alpaca, capture snapshots, schedule work, or advance paper lineage.
