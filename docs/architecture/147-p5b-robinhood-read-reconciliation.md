# Architecture 147 P5B-lite — Robinhood read/account/reconciliation

Status: source-only successor, pending exact-source acceptance and integration.
The accepted B1 binding and corrected B2 OPEN_REPLAY smoke precede this work.
There is no prolonged paper soak. P6 tiny explicitly armed live remains a
separate source/effect checkpoint with hard notional limits and separate review.

## Ownership and transport

`desktop_paper/robinhood_read.py` owns immutable typed account, portfolio,
position and order observations. `robinhood_reconciliation.py` owns the broker
baseline. `robinhood_mcp/current_read_transport.py` is additive to the frozen
Architecture 131 SDK transport; no private historical helper is reused and the
historical four-tool allowlist and source bytes are unchanged.

The current facade has exactly five provider methods: get_accounts,
get_portfolio, get_equity_positions, get_equity_quotes and get_equity_orders.
It has no public arbitrary-tool dispatch, review/preview, placement, cancel,
option or crypto method. The private dispatcher also rejects names outside
this set. It uses the public official Streamable HTTP endpoint constant
`https://agent.robinhood.com/mcp/trading` and the existing public Windows OAuth
factory. Construction is inert. Every actual read session discovers all five
required read tools before dispatch; unrelated advertised tools are discarded.
Discovery is capped at 20 pages per session and repeated cursors fail closed.
There is no retry loop or endpoint override.

## Baseline semantics

Canonical account resolution requires exactly one account whose
agentic_allowed is true, using the public existing resolver. Operator-entered
account numbers confer no authority. The exact account number stays in memory
for requests, is omitted from repr and is committed to evidence as lowercase
SHA-256 of its exact UTF-8 bytes. Account counts are bounded at 100.

Portfolio observations require finite decimal total value, cash, equity value,
buying power and unleveraged buying power, and consistent USD currency. They
are observation context only, including legitimate negative cash/deficits.
No conversion to PaperRuntimePolicy, RiskManager account authority, paper
balance or simulated fill exists.

Equity positions require canonical symbols, finite quantities and sellable
quantities, optional nonnegative average cost and consistent long/short/empty
classification. Observing a short holding does not enable short selling.
Unknown/boxed classification fails closed. Duplicate symbols, including
duplicates across pages, fail closed. Positions are sorted by symbol, capped
at 1,000 rows and three pages; repeated cursors fail closed.

SPY quotes use the public strict quote parser and current-trade selector.
Require exactly one SPY quote, active instrument, has_traded=true, finite
positive price material, and timezone-aware timestamps normalized to UTC.
The newer regular/non-regular trade is reported without a freshness or
execution-readiness claim. This observation never becomes a fill or advances
the P5 cursor.

Order history uses the canonical account, placed_agent=agentic and a fixed
seven-day UTC created_at_gte window. It is capped at three pages / 300 rows,
with no partial successful snapshot on exhaustion, malformed rows, repeated
cursors, duplicate order IDs or out-of-window/filter results. Canonical order
is created_at then order ID. The provider's agentic classification does not
identify this bot: every observed order remains unattributed.

The immutable reconciliation snapshot binds observed_at, account fingerprint
and counts, portfolio, canonical position tuple, SPY quote, bounded order tuple,
window, fixed status/diagnostics and local_expected_broker_effect_count=0.
Existing nonzero positions/orders are valid baseline data. Zero expected bot
effects does not assert zero account activity or reconciled future live effects.
Identical observations yield equal snapshots and canonical commitments without
ambient Decimal-context dependency. Missing/malformed observations fail closed.

## Registered protected-read boundary

`arch147-p5b-robinhood-read-reconcile` maps the exact
`feature/robinhood-p5b-read-reconcile-current` branch to GitHub-owned FULL.
Verify/admit/source authority are effect-free. execute=None. The unified
checkpoint runner owns the only later operator command; no second temporary
PowerShell/Python operator is introduced.

The registered preflight requires a canonical F: checkout, exact clean source,
canonical origin and matching feature/develop live heads plus integrated-source
authority. These checks precede provider access. A fresh external create-only
attempt marker precedes one bounded read sequence, and interrupted/partial
evidence remains visible. No automatic retry, cleanup or ambiguity repair is
permitted. The command is invoked only after separate ChatGPT exact-source and
effect review; registration/source PASS is not provider authorization.

Allowed future effects: necessary official OAuth/token-storage access,
capability discovery, the five reads and sanitized external evidence writes.
Maximum broker mutations, order reviews/previews, placements, cancels, P5
financial-state mutations, FINAL_HOLDOUT accesses and Alpaca calls are all zero.
The reader only hashes production SQLite/lifecycle and SQLite sidecars using
binary read opens. Before/after existence/hash identities must match. It never
opens SQLite through a database API or writes a lifecycle record.

Evidence schema: `arch147-p5b-robinhood-read-reconcile/v1`. It contains exact
source HEAD/tree, checkpoint, observed timestamp, account fingerprint/counts,
portfolio commitment/currency, position count/symbols/material commitment, SPY
prices/timestamps, order count/window/material commitment, required/observed
read tools, attempted tool-call counts (including failed calls), fixed zero
mutation counts, production before/after identities and credential-values-
exposed=false. It omits raw account numbers, tokens, credentials, raw provider
payloads, order IDs and unnecessary personal financial details. Failures use
fixed diagnostics and never serialize exception text or traceback.

The GUI displays cached NOT_CONNECTED, READ_ONLY_CONNECTED or
RECONCILIATION_FAILED with sanitized observation availability/counts and broker
mutation enabled=false. It has no Connect, Buy, Sell or Arm control, performs no
provider I/O, and claims no LIVE readiness. The accepted B1/B2 P5A path remains
independent: external bundle validation, 35/50 SPY binding, PAPER_EVALUATION,
live_eligible=False, OPEN_REPLAY, RiskManager/OrderEngine, kill/new-buy controls,
durable cursor and idempotency semantics are preserved.
