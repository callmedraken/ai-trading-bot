# Exact compact paper-ledger checkpoint state

## Boundary

The compact-state boundary exports one existing `PaperLedger` into immutable
exact accounting state and restores that state into one fresh `PaperLedger`.
It exists for a future checkpoint coordinator. It does not serialize JSON,
create genesis or successor checkpoints, execute a paper cycle, define lineage,
perform filesystem output, schedule work, or contact a provider or broker.

The boundary retains cash, ordered positions, exact quantity, exact total cost
basis, derived average cost, cumulative realized profit and loss, and one
explicit UTC as-of timestamp. Total cost basis is authoritative. It is never
reconstructed by multiplying quantity and average cost.

## Decimal policy and supported state

Arithmetic policy `compact-paper-ledger-arithmetic-v1` uses a private Decimal
context with precision 1024, `Emax=999999`, and `Emin=-999999`. Average cost is
derived as exact retained total cost basis divided by quantity in that context.
The retained average must equal that derivation.

Authoritative Decimal scalars accept at most 1024 significant digits, scale at
most 1024, and adjusted exponent at most 1024. Derived averages accept at most
1024 significant digits, scale at most 3072, and adjusted exponent at most
2048. All arithmetic and canonicalization are independent of the ambient
Decimal context. Signed zero is normalized to positive zero.

Cash is finite and nonnegative. Realized profit and loss is finite and may be
negative, zero, or positive. Each position has a unique exact `Symbol`, positive
finite quantity, and positive finite total cost basis. Position order is
preserved and is identity material. At most 100 positions are supported.

Positive cash without positions, zero cash with positive positions, and
positive cash with positions are supported. Zero cash without positions is
rejected even when realized profit and loss is nonzero because the current
`PaperLedger` cannot safely represent an account without positive cash or
positive position basis.

Exact types are required. Floats, booleans, integers used as Decimal fields,
strings used as domain scalars, nonfinite values, negative cash, nonpositive
position values, duplicate symbols, and out-of-bound values fail explicitly.

## Identity

Compact state uses dedicated namespace
`86b4402e-fdbc-56a1-85b6-a5dcfdf05f67` and material version
`compact-paper-ledger-state-v1`. Canonical scalars are UTF-8 byte-length framed.
Decimal text is exponent-free, context-independent, and normalizes every signed
zero to `0`.

The UUID5 material binds:

- material and arithmetic policy versions;
- normalized UTC as-of timestamp;
- cash and cumulative realized profit and loss;
- ordered position count and ordinal;
- symbol, quantity, exact total cost basis, and derived average cost;
- `EMPTY` history mode;
- the explicit `historical-fill-membership-empty` marker.

The new identity does not modify or replace existing engine or ledger
fingerprint versions.

## Restoration and reconciliation

Restoration creates a fresh ledger directly from exact retained accounting
values. It creates no synthetic buy or sell fill. Restored fill history and
duplicate-fill membership are intentionally empty. The public
`is_compact_restored` marker remains true after future fills so callers do not
mistake the retained history for complete lifetime evidence.

Restoration re-exports the fresh ledger under the same as-of timestamp and
requires exact model and compact-state UUID equality. It also checks exact cash,
realized profit and loss, empty fill history, and the compact-restored marker.
The existing ledger state UUID is calculated under the private arithmetic
context and retained as separate restoration evidence. Complete reconciliation
returns frozen, slotted evidence with `PASS`; failure returns no ledger/evidence
pair.

The restored ledger is accounting-equivalent for supported future buys and
sells because cash, quantity, exact total cost basis, and cumulative realized
profit and loss are identical. It is not observationally identical to its
source: historical fills, orders, lifecycle events, event and order IDs, and
duplicate-fill collision sets are deliberately outside this milestone.
