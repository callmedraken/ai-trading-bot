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


### 131-LQ — read-only live-qualification evidence verifier

Accepted. The side-foundation verifier deterministically reconciles the frozen
131-L live-qualification artifacts without gaining trading or provider
capability.

Accepted inputs and result:

```text
durable review-paper SQLite path opened with URI mode=ro
+ sanitized 131-H operator evidence JSON
+ sanitized 131-L qualification summary JSON
+ expected source HEAD/tree
+ exact predecessor order UUID
+ exact qualification order UUID
-> sanitized immutable verification result
```

The verifier freezes the exact accepted predecessor, including SPY BUY 1,
desired/approved quantity 1, APPROVED outcome, empty risk reasons, fill price
769.870000, zero commission, and fill timestamp
2026-10-03T00:00:00.232470+00:00. It also freezes the qualification branch,
proposal UUID, deterministic qualification mark, RESIZED 2 -> 1.000 decision,
risk-reason order, operator call counts, no replay, zero interactive
reauthorization, and the final two-record / 2.000-SPY durable state.

It imports no Robinhood MCP/OAuth transport and has no network, subprocess,
environment/config, retry, polling, scheduler, risk evaluation, review request,
paper fill, or performance-valuation capability. SQLite is opened read-only and
the verifier does not construct `ReviewPaperStore`.

Accepted source-only checkpoint:

```text
arch131-robinhood-live-qualification-verifier
preflight=None
execute=None
```

Accepted source and certification:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   49721d2607c01d2298447f494302cb5221afdf2a
TREE   6263431a90bc0e859ee4ef82d81c23351b17cae3
CI     #160 / 37110312724 SUCCESS

10,867 cases
10,856 passed
11 skipped
0 failed
0 errors
wall 526.681 s
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-8c29c7f1ed4b44ddbdc8c9663b5771d2
```

No live Robinhood/MCP/OAuth request or durable paper mutation occurred.

### 131-M — explicit-schedule regular-session admission

Accepted. The source-owned session-admission primitive classifies one explicit
instant against one already-authoritative immutable regular-session schedule.
It preserves the existing date-only `NYSEMarketCalendar` contract and does not
claim authority for holiday, early-close, or intraday schedule discovery.

Accepted composition:

```text
explicit timezone-aware as_of
+ exact immutable ReviewPaperSessionSchedule
  - exchange-local session_date
  - regular-session opens_at
  - regular-session closes_at
+ exact nonnegative opening_buffer
+ exact nonnegative closing_buffer
-> immutable ReviewPaperSessionAdmission
```

Accepted statuses and half-open boundaries:

```text
different America/New_York date              -> NON_SESSION_DATE
before opens_at                              -> BEFORE_REGULAR_WINDOW
[opens_at, admission_opens_at)               -> OPENING_BUFFER
[admission_opens_at, admission_closes_at)    -> ADMITTED
[admission_closes_at, closes_at)             -> CLOSING_BUFFER
at/after closes_at                           -> AFTER_REGULAR_WINDOW
```

All datetimes are timezone-aware and UTC-normalized. Open must precede close;
both endpoints must map to the supplied exchange-local date; exact
`timedelta` buffers must be nonnegative and leave a nonempty admissible
interval. Zero buffers are permitted.

The implementation reads no clock and has no schedule discovery, brokerage,
MCP, OAuth, market-data acquisition, paper-store, risk, intent, execution,
filesystem, network, subprocess, environment/config, UUID, retry, polling,
loop, scheduler, sleep, or durable-mutation capability.

Accepted source-only checkpoint:

```text
arch131-robinhood-session-admission
preflight=None
execute=None
```

Accepted source and certification:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   be4203bfdd37265fd4491712e4fb8292a5070bd1
TREE   25c9a9ca22478d3e626b8aef6d000f23496282bf
CI     #162 / 37139337294 SUCCESS

11,008 cases
10,991 passed
17 skipped
0 failed
0 errors
wall 522.892 s
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-bc214d8d6b724fb89f0e3541319cc091
```

No live Robinhood/MCP/OAuth request or durable paper mutation occurred.

### 131-N — canonical Robinhood quote-to-risk-price snapshot

Accepted. The source-owned quote boundary consumes one already-acquired typed
Robinhood equity-quotes response and emits one immutable canonical risk-price
snapshot without transport, provider, durable-store, or risk-evaluation
authority.

Accepted composition:

```text
typed RobinhoodEquityQuotesResponse
+ exact canonical required_symbols tuple
+ explicit observed_at
+ explicit positive max_quote_age
-> immutable ReviewPaperRiskPriceSnapshot
   - observed_at
   - canonical tuple of ReviewPaperRiskPriceMark
       symbol
       price
       source_at
   - derived read-only Symbol -> Decimal MappingProxyType
```

Accepted quote semantics:

- exact typed response and exact nonempty canonical unique `Symbol` tuple;
- quote-bearing results are indexed once and duplicate symbols fail closed;
- quote symbol set must exactly equal required symbols;
- `has_traded is True`;
- `state == "active"`;
- `RobinhoodQuoteData.current_trade_candidate()` is called exactly once per
  required symbol in canonical order;
- the newer regular/non-regular trade wins, with regular winning timestamp ties;
- selected price is exact `Decimal`, finite, and strictly positive;
- source timestamp is timezone-aware, UTC-normalized, and not in the future;
- exact max-age boundary is accepted; anything older fails closed;
- official-close material and `closes_error` are not risk-mark authority;
- output mapping is derived from immutable canonical marks and is read-only.

The implementation has no adapter/SDK transport, OAuth, account resolution,
quote acquisition, paper store/performance store, risk manager, 131-J/131-L,
execution, filesystem, environment/config, network, subprocess, UUID generation,
clock read, retry, polling, scheduler, sleep, or durable mutation capability.

Accepted source-only checkpoint:

```text
arch131-robinhood-risk-price-snapshot
preflight=None
execute=None
```

Accepted source and certification:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   a0c65ad559dacf6ce6121fcc0a1148b5c92adf78
TREE   78b3d663752ea18b7fae98fe12ef639fe8fdb3a8
PARENT 4dd1bea835b529cd9892bf21c5044a9d1b1c423d
CI     #164 / 37148921694 SUCCESS

11,136 cases
11,125 passed
11 skipped
0 failed
0 errors
wall 405.197 s
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-51708679d6c74d6ab74dc69365e46b1b
```

No live Robinhood/MCP/OAuth request or durable paper mutation occurred.

### 131-O — effect-free durable forward-paper risk preview

Accepted. The source-owned preview composes the exact accepted 131-N snapshot,
131-K durable virtual-account context, and one deterministic `RiskManager`
evaluation into immutable pre-review operator state.

Accepted composition:

```text
exact ReviewPaperStore
+ exact TradeProposal
+ exact ReviewPaperRiskPriceSnapshot
+ exact RiskLimits
+ exact new_trading_enabled bool
-> build_review_paper_risk_context exactly once
   using snapshot.prices
   and snapshot.observed_at
-> RiskManager(risk_limits).evaluate exactly once
-> immutable ReviewPaperForwardPreview
```

The preview preserves the exact proposal, price snapshot, risk limits, 131-K
`RiskContext`, and `RiskDecision`. Derived read-only properties are limited
to current/projected marked position quantity/value and projected total marked
market exposure.

Accepted projection rules:

- rejected risk leaves position/exposure unchanged;
- approved/resized BUY adds the approved quantity/notional;
- approved/resized SELL subtracts the approved quantity/notional;
- projections use only the accepted current mark and exact approved quantity;
- negative projected position or market exposure fails closed;
- explicit Decimal arithmetic is independent of ambient Decimal precision/traps.

The preview does not reconstruct the durable ledger independently and does not
reimplement cash/equity/position-coverage or risk constraints. It deliberately
does not produce projected post-fill cash/equity, realized P&L, fill price,
execution state, Robinhood review/checks/disclosures, an
`ExecutionInstruction`, or a `ReviewPaperIntent`.

The implementation has no provider adapter/transport, OAuth/account resolution,
quote acquisition, review call, intent bridge, 131-J/131-L invocation, order
execution/cancel, paper write, performance valuation, filesystem, network,
subprocess, environment/config, UUID generation, clock read, retry, polling,
scheduler, or sleep capability.

Accepted source-only checkpoint:

```text
arch131-robinhood-forward-paper-preview
preflight=None
execute=None
```

Accepted source and certification:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   47e3d6341848265752501d8376caad38bd5acb0f
TREE   04e5f54da0fbf03fdb1d5970777ca319c83be092
PARENT 7c1c088123beedb4e1303245190fcc2ea7228983
CI     #166 / 37155938112 SUCCESS

11,226 cases
11,209 passed
17 skipped
0 failed
0 errors
wall 497.582 s
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-81403e975caf4243ba9a7e6448b6ca51
```

No live Robinhood/MCP/OAuth request or durable paper mutation occurred.

### 131-P — bounded read-only Robinhood risk-price acquisition

Accepted. The source-owned acquisition boundary discovers the exact required
market-data symbols from the durable virtual account, performs one bounded read
through the accepted review/read adapter, records one UTC observation timestamp
after the typed response returns, and delegates all mark-selection and freshness
policy to 131-N.

Accepted composition:

```text
exact ReviewPaperStore
+ exact TradeProposal
+ exact RobinhoodReviewReadAdapter
+ exact positive max_quote_age
-> store.reconstruct_ledger exactly once
-> canonical open-position symbols U proposal symbol
-> reject >20 before provider access
-> adapter.equity_quotes(required_symbols) exactly once
-> datetime.now(UTC) exactly once after successful typed response
-> build_review_paper_risk_price_snapshot exactly once
-> exact ReviewPaperRiskPriceSnapshot
```

Accepted authority:

- malformed public inputs fail before durable reconstruction/provider access;
- required symbols are canonical, unique, nonempty, and limited to 20;
- only `RobinhoodReviewReadAdapter.equity_quotes` is called;
- provider/parser exceptions propagate unchanged with no clock read/retry;
- 131-N rejection propagates after one acquisition with no reacquisition;
- 131-P does not inspect/select prices or duplicate active/traded/freshness rules;
- durable account access is read-only symbol discovery only;
- no account resolution, order/review calls, risk evaluation, intent/execution,
  paper write, performance valuation, direct transport, filesystem, subprocess,
  environment/config, UUID generation, retry, polling, scheduling, or sleep
  authority exists.

Accepted source-only checkpoint:

```text
arch131-robinhood-risk-price-acquisition
preflight=None
execute=None
```

Accepted source and certification:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   adcf26ecdaa34fcdd85101fa0f82883cbbd7c752
TREE   7cddd4bfeb0c0d529e26182108a56acbd24fc174
PARENT a88ff4e5b25846e7c6d66bb7ff90c98b9f77e6b2
CI     #168 / 37167947385 SUCCESS

11,291 cases
11,280 passed
11 skipped
0 failed
0 errors
wall 495.919 s
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-ed5706f4c2d747c8a128d903d64a0518
```

Source certification made zero live Robinhood/MCP/OAuth requests and no durable
paper mutation.

### 131-Q — two-phase supervised forward-paper operator composition

Next side-foundation source milestone. 131-Q is the first coherent
operator-facing composition: prepare one current-session risk preview using
131-M/P/O, preserve the exact durable state that was reviewed, then require a
separate explicit proceed call before invoking accepted 131-L exactly once.

The prepare and execute phases are intentionally separate. Calling the execute
function is the explicit human proceed boundary; preparation must never invoke
131-L automatically.

Frozen preparation composition:

```text
exact ReviewPaperStore
+ exact TradeProposal
+ exact authoritative ReviewPaperSessionSchedule
+ exact opening/closing buffers
+ exact RobinhoodReviewReadAdapter
+ exact max_quote_age
+ exact RiskLimits
+ exact new_trading_enabled bool

-> prepare_started_at = datetime.now(UTC) exactly once
-> 131-M admission at prepare_started_at exactly once
-> if not ADMITTED:
     return SESSION_NOT_ADMITTED
     zero quote reads / zero preview / zero 131-L

-> durable_history_before = store.history() exactly once
-> 131-P exactly once
-> 131-M admission at price_snapshot.observed_at exactly once
-> if not ADMITTED:
     return SESSION_EXPIRED_DURING_ACQUISITION
     snapshot preserved
     zero preview / zero 131-L

-> 131-O exactly once
-> durable_history_after = store.history() exactly once
-> require durable_history_before == durable_history_after
-> compute quote_valid_until from the accepted 131-N marks and max_quote_age
-> RISK_REJECTED if preview decision rejected
   else READY_TO_PROCEED
-> immutable ReviewPaperSupervisedPreparation
```

Frozen preparation statuses:

```text
SESSION_NOT_ADMITTED
SESSION_EXPIRED_DURING_ACQUISITION
RISK_REJECTED
READY_TO_PROCEED
```

A prepared READY result preserves exactly:

- the exact store object;
- proposal, schedule, opening/closing buffers, max quote age, risk limits, and
  trading-enabled flag;
- initial 131-M admission;
- exact 131-P price snapshot;
- quote-time 131-M admission;
- exact 131-O preview;
- exact stable durable history tuple observed around acquisition/preview;
- `quote_valid_until`, defined as the earliest
  `mark.source_at + max_quote_age` across the accepted snapshot marks.

Preparation validation must make optional fields/status combinations
self-consistent. `quote_valid_until` must be timezone-aware/UTC and cannot
precede the snapshot observation time. If timestamp addition overflows, fail
closed rather than extending validity.

Frozen explicit proceed composition:

```text
exact READY_TO_PROCEED preparation
+ exact ExecutionInstruction
+ exact caller-owned order_id
+ explicit accepted 131-L non-store configuration

-> execute_at = datetime.now(UTC) exactly once
-> 131-M admission at execute_at exactly once
-> require ADMITTED
-> require execute_at <= preparation.quote_valid_until
-> 131-O exactly once using the same store/proposal/snapshot/limits/flag
-> require revalidated risk_context == prepared risk_context
-> require revalidated risk_decision == prepared risk_decision
-> current_history = store.history() exactly once
-> require current_history == preparation.durable_history
-> require instruction.created_at >= prepared decision.evaluated_at
-> run_robinhood_forward_paper_cycle exactly once using:
     same exact store
     same proposal
     prices = preparation.price_snapshot.prices
     as_of = preparation.price_snapshot.observed_at
     same new_trading_enabled
     same risk_limits
     supplied instruction/order_id/config
     review_received_at = execute_at
-> require returned risk_decision == revalidated risk_decision
-> immutable ReviewPaperSupervisedExecutionResult
```

The execute call does not reacquire market data. A human-approved preparation is
valid only while its accepted quote marks remain within the same explicit max
age and the session remains admitted. If it expires, account state changes, or
risk revalidation differs, execution stops before 131-L and the caller must
prepare/review a fresh preview.

The durable-history equality checks are a supervised drift guard, not a new
account authority. 131-O/131-K remain the account/risk authority. 131-L still
reconstructs/evaluates at its accepted boundary immediately before its existing
review-paper pipeline. 131-Q must compare the returned 131-L risk decision to
the pre-effect revalidation and fail closed if an unexpected race is observed;
it must never retry.

Frozen execution inputs forwarded to 131-L remain explicit:

- `ExecutionInstruction`;
- caller-owned `UUID order_id`;
- expected branch/HEAD/tree;
- evidence path;
- redirect URI;
- slippage basis points;
- commission.

131-Q does not generate proposal/order identities, schedules, execution
instructions, or operator configuration. It does not create a second store and
does not accept independent paper-store path/starting cash.

131-Q may call only these accepted project boundaries:

- `admit_review_paper_session`;
- `acquire_review_paper_risk_price_snapshot`;
- `build_review_paper_forward_preview`;
- `ReviewPaperStore.history` for exact drift guards;
- `run_robinhood_forward_paper_cycle` in the explicit execute phase.

It must not call MCP/SDK transport, OAuth/account resolution, quote adapter
methods directly, 131-K/J/I/H directly, `RiskManager` directly, store mutation,
performance valuation, order placement/cancel/options/crypto, filesystem APIs
outside values already required by 131-L, subprocess, environment/config,
retry, polling, scheduler, or sleep.

Source certification uses doubles at 131-P and 131-L boundaries and performs zero
live Robinhood/MCP/OAuth requests and zero durable paper writes. The source-only
checkpoint does not itself expose preflight/execute callbacks.

Planned checkpoint:

```text
arch131-robinhood-supervised-forward-paper
preflight=None
execute=None
```

The checkpoint follows 131-P in the side-foundation optimized batch. After
source/broad certification, the next protected work is a bounded supervised
qualification of the prepare path/read-only quote boundary and, separately,
explicit authorization for a real 131-Q paper execution. Production/live real
order placement remains NO-GO.

## D10 disposition

D10 remains frozen historical infrastructure with its scheduler disabled.
Architecture 131 does not restart or reuse the failed D10 unattended soak.
