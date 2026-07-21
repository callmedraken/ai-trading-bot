# Paper fill generation

The paper-fill generator purely determines immutable candidate fills for a
validated `PaperSubmissionBatchResult`. It does not apply those candidates to
an order engine or ledger and does not change orders, cash, positions, cost
basis, or profit and loss.

## Request and eligible source

`PaperFillBatchRequest` contains a caller UUID, complete submission result,
explicit aware fill timestamp, ordered order-ID keyed reference prices,
explicit fill policy, and ordered metadata. Timestamps normalize to UTC and no
clock or generated request identity is used. Prices must match submitted source
order IDs exactly and in order; missing, extra, duplicate, and reordered inputs
fail closed.

A SUBMITTED source contains aligned unique submitted orders and events. Orders
must be unfilled MARKET DAY orders without limit prices, retain their complete
positive requested quantity, and have a matching SUBMITTED event. Fill time may
equal or follow submission and request creation. A NO_ACTION source requires no
prices and returns one stable diagnostic with no evaluations.

## Full fills, prices, and commission

The initial policy generates exactly one full candidate per source order. No
partial ratios, liquidity limits, scheduling, merging, or splitting occur.
Reference prices, basis points, commissions, quantities, and calculated prices
use finite `Decimal` values without quantization or tick rounding.

For `s = slippage_basis_points / 10000`, slippage amount is
`reference_price * s`. Buys add the amount and sells subtract it, matching the
existing deterministic backtest convention. Basis points are at least zero and
less than 10000, keeping sell prices positive. One explicit fixed nonnegative
commission is copied to every candidate and is not inferred from risk limits.

## Traceability, identity, and atomicity

Submission order is preserved. Each immutable `PaperFillEvaluation` retains
the source ordinal, reference price, nonnegative slippage amount, and generated
`OrderFill`. Its fill maps exactly to the source order's identity, symbol, side,
and full quantity.

Fill UUID5 identity uses `paper-fill-v1`, request and source-result identity,
source ordinal, order and submitted-event IDs, side, canonical quantity and
price inputs, policy, final price, and fill timestamp. Result identity includes
the canonical request, ordered evaluation details and fill IDs, status, and
diagnostic codes. Decimal identity text is finite, exponent-free,
locale-independent, and normalizes negative zero.

Generation validates every input and derives every candidate value and ID
locally before constructing fills. Evaluations are reconciled and the immutable
result is constructed last. Failure returns no partial result and needs no
shadow state because the operation is pure.

## Generated is not applied

An `OrderFill` returned here is a generated, unapplied candidate. The source
order remains SUBMITTED; no `OrderEngine.apply_fill` call, lifecycle event,
engine fill-history change, ledger entry, or accounting change occurs. A future
atomic fill-application layer must revalidate live engine and ledger state,
apply candidates to both shadow components, reconcile them, and only then
replace authoritative state. Partial fills, volume and liquidity simulation,
market-data integration, brokerage, persistence, and networking remain
deferred.
