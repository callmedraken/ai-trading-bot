# Architecture 131 — Robinhood Review-Based Paper Trading

## Decision

Paper mode uses the connected Robinhood Trading MCP only for review/read
operations. It never calls `place_equity_order`, `cancel_equity_order`, or any
other order-changing tool.

The actual connected MCP exposes `review_equity_order`,
`get_equity_quotes`, and `get_equity_orders`, but does not expose the
trade-approval management tools originally assumed by the earlier design.

The architecture is therefore:

```text
third-party AI / research
        |
        v
TradeProposal
        |
        v
deterministic RiskManager
        |
        v
ExecutionInstruction
        |
        v
Robinhood review_equity_order
        |
        +--> quote_data + order_checks + disclosure
        |
        v
durable synthetic paper fill
        |
        v
virtual PaperLedger / P&L
```

No real Robinhood order is intentionally created.

## Robinhood review contract

Phase A supports share-quantity MARKET equity/ETF orders during regular hours.
The MCP paper-cycle boundary must resolve the canonical equities account
internally from Robinhood MCP account metadata, require exactly one account with
`agentic_allowed=true`, and pass that account's exact MCP `account_number`
together with the exact risk-approved quantity. Operator-entered app-visible
account numbers are not authoritative MCP identity.

The review response must echo the expected symbol, side, order type, and
quantity. The response's quote_data is the fill quote; no second immediate quote
call is required.

The exact `market_data_disclosure` and canonical `order_checks` object are
retained with the paper record. Any operator-facing view must preserve the
market-data disclosure verbatim.

## Synthetic fill policy

For a valid review quote:

```text
BUY  = ask_price * (1 + slippage_bps / 10000)
SELL = bid_price * (1 - slippage_bps / 10000)
```

BUY fill time is the review quote's venue_ask_time.
SELL fill time is the review quote's venue_bid_time.

The reference bid/ask must be positive, the instrument must have traded, and
the listing state must be `active`. The quote timestamp must not precede the
local TradeProposal timestamp.

Slippage and commission are explicit durable inputs.

## Virtual account

Paper mode owns an independent virtual account. Starting cash is explicit
configuration and is not inferred from real Robinhood buying power.

Risk evaluation for paper mode must use the virtual PaperLedger state:

- cash,
- positions,
- equity,
- exposure,
- current market price.

Robinhood portfolio/account data may be research context but cannot silently
become paper-risk state.

## Durable identity

One synthetic paper trade is keyed by the local broker-independent order_id.

```text
paper_trade_id = UUID5(review-paper namespace, order_id)
fill_id        = UUID5(review-fill namespace, order_id)
```

Re-observing the same exact order/review is idempotent. Reusing an order_id with
different review or trade material is a hard conflict.

The durable record retains:

- proposal_id and order_id,
- AI proposal reason/confidence,
- desired and risk-approved quantity,
- risk outcome and reason codes,
- symbol / side / type / TIF,
- Robinhood review capture time,
- exact market_data_disclosure,
- canonical order_checks JSON,
- review quote values and venue timestamps,
- simulated slippage and commission,
- deterministic paper_trade_id and fill_id,
- synthetic fill price/time.

## Real-order safety assertion

The later MCP orchestration checkpoint may use `get_equity_orders` before and
after review as read-only evidence that review did not create a real order.
The observer should narrow by account, `placed_agent=agentic`, and an exact
time window when possible.

An attributable new order is a terminal paper-mode safety violation.

`get_equity_orders` is not the paper ledger and cannot replace durable local
paper history.

## Mark-to-market

Later valuation uses `get_equity_quotes` and the existing PaperLedger snapshot
logic. Current price selection/freshness belongs to the Robinhood read adapter,
not the accounting core.

## Tool surface exposed to the AI

The model never receives raw MCP mutation tools.

Paper-mode application allowlist:

```text
review_equity_order
get_equity_quotes
get_equity_orders
other explicitly reviewed read-only research tools
```

Forbidden from the model/tool facade:

```text
place_equity_order
cancel_equity_order
place_option_order
cancel_option_order
exercise_option
place_crypto_order
cancel_crypto_order
```

## Checkpoints

### 131-A2 — review-paper accounting core

Registered source gate:

```text
arch131-robinhood-review-paper
```

Network-free implementation of review models, deterministic fill policy,
SQLite durability, idempotency, and PaperLedger reconstruction.

### 131-B — Robinhood read/review transport

Implement typed parsing for the observed MCP schemas and capability discovery.
No placement/cancel tools.

### 131-C — paper-cycle orchestration

Bind AI -> deterministic risk -> review -> durable paper fill, with read-only
real-order guard evidence.

### 131-D — performance tracking

Add forward-test valuation/reporting: realized/unrealized P&L, total return,
drawdown, win/loss rate, and model/strategy attribution.

### 131-E — direct Robinhood MCP transport

Use the official MCP Python SDK over Streamable HTTP with the public application
surface frozen to `review_equity_order`, `get_equity_quotes`, and
`get_equity_orders`.

### 131-F — Windows OAuth persistence and callback

Persist OAuth token/client-registration state only in reviewed Windows
Credential Manager records and use the bounded loopback callback flow.

### 131-G — canonical Agentic-account resolution

Resolve Robinhood account metadata internally, require exactly one equities
account with `agentic_allowed=true`, and use its MCP `account_number` for
the complete paper cycle. `get_accounts` remains internal and is not exposed
to the AI/application facade.

### 131-H — source-owned paper operator

Accepted. One-cycle Robinhood review-paper operation now lives in a deterministic
source-owned operator with explicit source/output admission, sanitized evidence,
no interactive reauthorization, and no real-order mutation capability.

After any attempted review, post-review agentic order history is always exhausted
before the cycle may finish. A post-review safety/read failure takes precedence
over a review failure; a clean post-window re-surfaces the original review
failure. Only a valid review and proven-empty post-review window may create the
local synthetic paper fill.

The registered source-only checkpoint is
`arch131-robinhood-paper-operator`.

### 131-I — deterministic risk-to-paper-intent bridge

Accepted. The pure `build_review_paper_intent` boundary converts an existing
`RiskDecision`, `ExecutionInstruction`, and explicit caller-supplied local
order UUID into the exact `ReviewPaperIntent` consumed by 131-H.

The bridge preserves proposal, risk-decision, reason-code, execution-instruction,
and order identity material exactly. It performs no risk reevaluation, order
submission, Robinhood/MCP/OAuth/credential access, environment/config access,
filesystem/network/subprocess activity, or logging.

The registered source-only checkpoint is
`arch131-robinhood-paper-intent-bridge`.

The full deterministic proposal -> risk -> execution instruction -> intent
bridge -> source-owned paper operator path has now passed one bounded live
qualification.

### 131-J — source-owned deterministic paper pipeline

Accepted. The source-owned one-cycle pipeline accepts explicit `TradeProposal`,
`RiskContext`, `RiskLimits`, `ExecutionInstruction`, caller-supplied local
order UUID, and the existing 131-H operator configuration.

It evaluates risk exactly once, returns rejected decisions locally before
brokerage/operator effects, sends APPROVED/RESIZED decisions through the
accepted 131-I bridge exactly once, and delegates accepted paper review to the
accepted 131-H operator exactly once.

The result is immutable and preserves the exact `RiskDecision`,
`ReviewPaperIntent`, and sanitized `RobinhoodPaperOperatorEvidence` boundaries.
No scheduler, retry loop, OrderEngine submission, direct MCP/OAuth capability,
real brokerage balance as risk state, mutation-tool surface, or unattended mode
is introduced.

The registered source-only checkpoint is
`arch131-robinhood-deterministic-paper-pipeline`.

The source-owned 131-J pipeline has now passed one bounded live qualification.

### 131-K — durable virtual-paper risk context

Accepted. The source-owned `build_review_paper_risk_context` boundary derives
the exact 131-J `RiskContext` from durable virtual paper history rather than
caller-invented account balances.

It reconstructs `ReviewPaperStore` exactly once, requires an exact explicit
price snapshot for every open virtual position plus the proposal symbol, creates
one marked `AccountSnapshot`, and maps that state exactly into `RiskContext`.
Real Robinhood balances, positions, portfolio values, and buying power remain
non-authoritative for paper risk.

The accepted source-only checkpoint is
`arch131-robinhood-virtual-risk-context`. It has no preflight or execute
capability and remains network-free, mutation-free, identity-free, and free of
risk-manager, pipeline, operator, retry, loop, or scheduler behavior.

Accepted source and certification:

```text
HEAD 30c30a4141bc45f20a4fd1bf87ec6c40d7091dca
TREE f6e11a8593482c3e29eda5187589dfa85a3e3a39
CI   #149 / 37103825469 SUCCESS

10,717 cases
10,706 passed
11 skipped
0 failed
0 errors
wall 454.629 s
```

### 131-L — human-started durable-context forward-paper cycle

Accepted. The source-owned `run_robinhood_forward_paper_cycle` binder composes
the accepted 131-K durable virtual-paper risk context with the accepted 131-J
deterministic paper pipeline without creating a second risk, brokerage, or
paper-state implementation.

Accepted composition:

```text
ReviewPaperStore durable history (sole paper-account identity)
+ TradeProposal
+ explicit exact price snapshot
+ explicit as_of / new_trading_enabled
+ RiskLimits
+ ExecutionInstruction
+ caller-supplied local order_id
+ explicit non-store 131-H operator configuration
-> build_review_paper_risk_context(store, ...) exactly once
-> exact returned RiskContext
-> run_robinhood_deterministic_paper_pipeline exactly once
   with paper_store_path = store.path
   and starting_cash = store.starting_cash
-> exact existing RobinhoodDeterministicPaperPipelineResult
```

The caller supplies exactly one `ReviewPaperStore`, which is the sole
paper-account identity for both risk and the later synthetic paper write. The
public binder accepts no independent `paper_store_path`, `starting_cash`, or
`risk_context` input.

The binder does not reconstruct the ledger independently, evaluate risk
independently, bypass 131-J, call the intent bridge/operator/raw
Robinhood/MCP/OAuth/account-resolution boundary directly, infer paper risk from
the real brokerage account, generate order identity, retry, poll, loop, schedule,
or introduce unattended operation. Placement/cancel/options/crypto mutation
remains absent.

The accepted source-only checkpoint is
`arch131-robinhood-forward-paper-cycle`, immediately after 131-K in the
optimized batch. It has `preflight=None` and `execute=None`.

Accepted source and certification:

```text
HEAD 97ab6b89931c105726944dc9609a9e0de062bac6
TREE 8942f72bebed58cb7536f227b866b7818b5ac513
CI   #152 / 37105712512 SUCCESS

10,820 cases
10,809 passed
11 skipped
0 failed
0 errors
wall 412.828 s
```

No live Robinhood/MCP activity occurred during source implementation or
certification.

The next boundary is one bounded live qualification of the accepted 131-L
human-started forward-paper cycle. That qualification may perform exactly one
non-placement `review_equity_order` and therefore requires fresh explicit
authorization. Production/live order placement remains NO-GO.

## D10 disposition

D10 remains frozen historical infrastructure with its scheduler disabled.
Architecture 131 does not restart or reuse the failed D10 unattended soak.
