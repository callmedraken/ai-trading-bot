# Deterministic paper portfolio simulation

## Purpose and boundary

The `simulation` package coordinates an ordered, caller-supplied sequence of
frames through one `PaperPortfolioRuntime`. It derives current portfolio state
from the authoritative paper ledger but delegates planning, proposal creation,
risk, orders, submission, fills, and accounting to the existing runtime.

It does not fetch market data, invoke strategies or optimization, contact a
broker, schedule work, persist state, run a historical backtest, calculate
performance analytics, or use GPU or AI functionality.

## Frames and state derivation

A frame supplies an explicit UTC valuation time, target, ordered risk and fill
prices, policies, limits, commission assumptions, submission/fill times, and
metadata. Tuple position is its canonical ordinal. Frames never accept a
`PortfolioState`.

Immediately before a cycle, the simulator reads current ledger cash and
positions. It creates one ordered state entry per target/price symbol, retaining
owned quantity and average cost and using zero quantity and cost for unowned
symbols. Equity is cash plus quantity times the explicit risk price. Fill
reference prices never value state. Every held symbol must remain in the target
universe, including at zero target weight for liquidation.

## Chronology and identity

Frame, target, and derived-state timestamps are equal. Each frame satisfies
`as_of <= submitted_at <= filled_at`. Frame valuation times strictly increase,
and each next valuation is at or after the previous fill time.

UUID5 identities use `paper-portfolio-simulation-v1`. The first cycle ID
includes the request, ordinal, normalized timestamp, complete canonical frame,
and initial engine and ledger fingerprints. Later cycle IDs replace initial
state with the immediate prior cycle result ID, including after `NO_ACTION`.
The result identity includes the canonical request, ordered frames and cycle
results, initial/final state IDs, counts, status, and diagnostic codes.

## Ownership, audit, and atomicity

The simulator owns one runtime reference; its engine and ledger properties
delegate dynamically because successful runtime cycles replace those objects.
Each immutable evaluation retains its frame, derived state, cycle result, and
pre/post fingerprints. Adjacent fingerprints must chain, and final result IDs
must match both the last evaluation and live runtime before return.

Atomicity is per frame. Earlier successful frames remain committed if a later
frame fails. The failed runtime cycle commits nothing, later frames are not
attempted, and no simulation result is returned. The raised simulation cycle
error records the failed ordinal and preserves the runtime error as its cause.
There is no rollback, partial-result contract, crash recovery, or persistence.

`COMPLETED` means every frame succeeded and at least one cycle applied.
`NO_ACTION` means every cycle took no action and carries one stable diagnostic.

## Relationship and deferred work

This runner exercises production-style runtime composition with deterministic
frames. It does not replace historical backtest engines, which provide market
data sequencing, strategy boundaries, and look-ahead protection. Future work
may add target-generation adapters, historical-data adapters, analytics,
scheduled paper operation, persistence/recovery, or richer fill models without
changing this version's deterministic ownership and audit rules.
