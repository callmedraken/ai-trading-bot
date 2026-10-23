# Architecture 132-R3J — ROBINHOOD timing-aware topology validation

## Scope and boundary

R3J changes only current ROBINHOOD lane placement. It is based on exact R3
HEAD `b40038c16a93f9bd9eb46cba5a30c14ba23b48ec` and tree
`f3fada1c83feb2ed04b9397a4c795db8454e8a69`. It does not change product,
runtime, strategy, risk, broker, paper, D1S3 operator, FULL, LEGACY,
EXHAUSTIVE, workflow topology, protected authority, or the parked unpublished
R4 worktree.

## Evidence derivation

The only topology evidence is the preserved GitHub Actions run `39903070805`
and artifact `canonical-certification-robinhood`, whose digest is
`sha256:5b8af9ad5c731cd74c3c83f6c635cd0c9c6eef6f9558bbad3d3ded20e5cd1a6f`.
The artifact contains `robinhood-1.xml` and `robinhood-2.xml`. For every
testcase, the canonical module is the testcase classname with dots replaced by
forward slashes and `.py` appended. Each testcase duration is converted to a
positive integer millisecond contribution and summed by module. No runtime
certification path reads this artifact.

The derivation must produce 109 modules, 543684 total milliseconds, and no
zero-total module. The sorted compact JSON object of canonical module to total
milliseconds must hash to:

```text
b4e7b62c1c63e273546cc83c324be6634d7809a8194540b27f950117dce73c99
```

The source table is a tuple of pairs. Validation rejects non-tuple material,
malformed entries, noncanonical paths, duplicate semantic paths, stale paths,
nonpositive weights, and bool weights. Every current R3 selected module has a
frozen entry. A future admitted ROBINHOOD module absent from the table receives
exactly 1000 ms for placement and is never excluded from coverage.

## Placement acceptance

The model uses exactly two lanes, whole modules, descending frozen/fallback
weight, ascending canonical path, lowest modeled total, and lowest lane index
for ties. Assignment order is preserved. The R3 inventory must produce:

```text
robinhood-1: 54 modules, 271842 ms
robinhood-2: 55 modules, 271842 ms
```

For each lane, UTF-8 canonical paths joined by newline with one final newline
must hash to:

```text
robinhood-1  91b85f6104620e3040821b3a55cf9b8875e54c9d47b6ac0532e4808c5d46eb24
robinhood-2  96bae036e5cd7f7b5148a3402151351c16a1bcc3a01b412d58f8de941147e99f
```

The D1S3 operator test must remain in `robinhood-2` with 10946 ms. Reversed
inventory input must produce identical ordered lanes. Changing the bytes or
size of an existing selected module without changing inventory or frozen
timings must produce exact lane equality, proving byte independence.

## Compatibility and authority acceptance

The four historical ROBINHOOD pin dictionaries retain their exact values but
are inactive in current `build_lanes`. FULL remains byte/behavior unchanged;
LEGACY and EXHAUSTIVE remain unchanged. R3J is deliberately absent from
`ACTIVE_CI_CHECKPOINTS` and `CI_CERTIFICATION_PROFILES`; resolving its push
branch returns `None`, so source-gate CI uses the reviewed unmapped broad
fallback. The checkpoint-runner successor overlay validates the accepted D1S3
predecessor material before substituting only the three changed certification
consumers, preserving R2 `None` rollback and mutable-current-doc handling.

R3J acceptance requires focused lane/profile/source/authority tests, Ruff
check and format-check on changed Python files, `git diff --check`, and a
plan-only ROBINHOOD run showing the exact model above before publication. After
terminal-green unmapped source-gate CI, exactly one canonical local ROBINHOOD
run may provide distinct topology evidence. No FULL or protected operation is
part of R3J.
