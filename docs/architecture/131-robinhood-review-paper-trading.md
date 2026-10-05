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

Accepted. 131-Q is the first coherent operator-facing composition: prepare one current-session risk preview using
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

Accepted source-only checkpoint:

```text
arch131-robinhood-supervised-forward-paper
preflight=None
execute=None
```

The checkpoint follows 131-P in the side-foundation optimized batch.

Accepted source and certification:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   577393185fa244f81a37d5b898454c883bcec6cf
TREE   7ea902274d7f56abaf3ccc1d38a605193ea21a2d
PARENT 63529780a14800fa0e909dd65bce22c9def5a12b
CI     #170 / 37187325071 SUCCESS

11,444 cases
11,433 passed
11 skipped
0 failed
0 errors
wall 425.341 s
```

Evidence:

```text
F:\\AI\\temp\\pytest\\certification-evidence-e75178913a21469bbea2267da2dc35ad
```

Source/broad certification used doubles/fakes and performed zero live
Robinhood/MCP/OAuth requests and zero durable paper writes.

### Protected operational sequence after 131-Q source acceptance

No further source milestone is required before bounded qualification of the
accepted supervised flow. The protected sequence is intentionally split:

1. complete the already-authorized first live 131-L qualification on the frozen
   `feature/robinhood-review-paper-mode` branch and reconcile it with 131-LQ;
2. separately authorize one bounded 131-Q PREPARE qualification on the accepted
   side-foundation source, permitting only the existing read-only quote path and
   no 131-L execution;
3. after the prepare qualification is accepted, separately authorize one 131-Q
   EXECUTE qualification, which may invoke accepted 131-L exactly once and may
   create one synthetic paper fill if all current session/freshness/drift/risk
   checks remain satisfied.

A PREPARE qualification must stop after producing operator-visible preparation
state. It must not use the fact that preparation returned READY_TO_PROCEED as
implicit permission to execute. PREPARE and EXECUTE are distinct protected
authorizations.

Any real 131-Q qualification must preserve the accepted no-retry rule. Provider
failure, stale quote, session expiry, drift, ambiguous review outcome, or any
post-authorization failure does not create retry authority.

Production/live real brokerage placement remains NO-GO.

### 131-R — PREPARE qualification harness and read-only evidence verifier

Optional qualification-support milestone. 131-R does not extend the trading
pipeline and is not a prerequisite for the already-authorized 131-L
qualification. It exists to make the later protected 131-Q PREPARE
qualification source-owned, reproducible, and independently reconcilable.

131-R has two source surfaces:

```text
A. PREPARE qualification harness
B. read-only PREPARE evidence verifier
```

#### A. PREPARE qualification harness

Frozen inputs:

```text
exact ReviewPaperStore
+ exact TradeProposal
+ exact ReviewPaperSessionSchedule
+ exact opening/closing buffers
+ exact RobinhoodReviewReadAdapter
+ exact positive max_quote_age
+ exact RiskLimits
+ exact new_trading_enabled bool
+ expected source HEAD/tree
+ fresh absolute evidence path
```

Frozen sequence:

```text
validate all non-provider inputs
-> read exact SQLite metadata + full review_fills rows using URI mode=ro
-> canonicalize and hash PREPARE-BEFORE durable snapshot
-> prepare_review_paper_supervised_cycle(...) exactly once
-> read exact SQLite metadata + full review_fills rows again using mode=ro
-> canonicalize and hash PREPARE-AFTER durable snapshot
-> require BEFORE == AFTER exactly
-> serialize one sanitized evidence document
-> write evidence once to a fresh path
-> return the exact ReviewPaperSupervisedPreparation
```

The harness may call only the accepted 131-Q PREPARE function. It must not import
or call `execute_review_paper_supervised_cycle`,
`run_robinhood_forward_paper_cycle`, 131-J/I/H, RiskManager, direct adapter
methods, transport, OAuth/account resolution, store mutation, performance
valuation, placement/cancel/options/crypto, retry, polling, scheduler, or sleep.

The harness must never infer that `READY_TO_PROCEED` authorizes execution.
Evidence must state explicitly that no supervised EXECUTE/pipeline result was
produced by this harness.

The durable snapshot fingerprint covers:

- complete ordered metadata rows;
- complete ordered `review_fills` rows and all columns;
- canonical JSON encoding;
- SHA-256 digest;
- row count.

The harness reads SQLite only through a read-only URI. It must not construct a
second `ReviewPaperStore`, initialize schema, migrate, insert, update, or
delete.

Frozen sanitized evidence schema:

```text
schema = arch131-q-prepare-qualification/v1
source_head
source_tree
store_path
starting_cash
proposal:
  proposal_id
  symbol
  side
  desired_quantity
  created_at
schedule:
  session_date
  opens_at
  closes_at
opening_buffer_seconds
closing_buffer_seconds
max_quote_age_seconds
new_trading_enabled

durable_before:
  metadata
  record_count
  sha256

preparation:
  status
  initial_admission
  price_snapshot | null
  quote_admission | null
  risk_preview | null
  quote_valid_until | null

durable_after:
  metadata
  record_count
  sha256

execute_invoked = false
pipeline_result_present = false
```

Where present, `price_snapshot` records only accepted 131-N marks
(symbol/price/source_at/observed_at), and `risk_preview` records sanitized
requested quantity, risk outcome, approved quantity, reason codes, marked
cash/equity/current price/exposure, current/projected position quantity/value,
and projected total exposure. No OAuth credential, account identifier, raw
transport payload, order-check disclosure, or secret-bearing data belongs in
131-R evidence.

Evidence path must be an absolute `Path`, must not already exist, and must not
be the durable SQLite path. Failure after the provider read does not create
retry authority; a later real qualification requires a new explicit
authorization and a fresh evidence path.

#### B. PREPARE evidence verifier

The verifier is provider-free and opens the durable SQLite only with URI
`mode=ro`. Inputs:

```text
evidence JSON
+ durable store path
+ expected source HEAD/tree
+ expected proposal UUID
-> immutable sanitized verification result
```

It independently verifies:

- exact schema/source/proposal/store identity;
- exact durable metadata;
- PREPARE before/after digests are equal;
- current read-only SQLite digest equals the recorded before and after digest;
- evidence record counts equal the current durable record count;
- `execute_invoked == false`;
- `pipeline_result_present == false`;
- status/optional-field combinations match accepted 131-Q preparation semantics;
- quote marks are canonical/nonempty when a snapshot is present;
- `quote_valid_until` equals the earliest mark source time plus exact max age
  for completed preview states;
- RISK_REJECTED carries a rejected risk result;
- READY_TO_PROCEED carries APPROVED or RESIZED risk result;
- session-blocked states carry no execution-capable preview material.

The verifier must not import adapter/transport/OAuth, call a provider, construct
`ReviewPaperStore`, evaluate risk, invoke 131-Q, or mutate the filesystem/store.

Planned source-only checkpoints:

```text
arch131-robinhood-supervised-prepare-qualification
arch131-robinhood-supervised-prepare-verifier
preflight=None
execute=None
```

Both follow 131-Q on the side-foundation batch. Source certification uses a real
review adapter around fake transport for the harness and fixture SQLite for the
verifier. It performs zero live Robinhood/MCP/OAuth requests and no durable
paper mutation.

A later real 131-Q PREPARE qualification remains a protected read-only provider
effect requiring fresh explicit user authorization. 131-R source acceptance
does not grant that authorization and does not grant 131-Q EXECUTE authority.


#### 131-R accepted source/certification

131-R is fully accepted after exact source review, one direct verifier hardening
commit, source-gate CI, and broad local certification.

Accepted source identity:

```text
BRANCH feature/robinhood-review-paper-side-foundation
HEAD   15d69c5bc12803ce71f6f2bd5151f53bc2432f6d
TREE   58de4e2e5c943c81cfa8179dd52b51620c86f490
PARENT 32b15e714a5925bf1bd5844025d8c2ef50605c33
CI     #174 / 37230454534 SUCCESS

11,657 cases
11,646 passed
11 skipped
0 failed
0 errors
wall 462.356 s
```

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-c893b92f948b4495927699e109d3fc9a
```

Accepted verifier hardening additionally requires exact paper metadata
(`schema_version=2`, matching starting cash, no unexpected metadata keys),
independently recomputes session-admission status from each evidence timestamp,
validates the schedule's America/New_York session date, and rejects a completed
preview whose earliest accepted quote deadline predates its observation time.

No live Robinhood/MCP/OAuth request, supervised EXECUTE, synthetic fill, or
protected durable mutation occurred during source/broad certification.

### 131-S — versioned NYSE regular-session schedule authority

131-S is **ACCEPTED/CERTIFIED**. It supplies the published intraday-schedule
authority without adding provider or execution authority. Integrating that
authority into supervised PREPARE/qualification composition is separate
follow-on source/design work; its exact contract is not yet frozen.

The authority is deliberately bounded to the NYSE-published 2026-2028 equity
calendar currently used for qualification/product development. It must not
pretend to know unpublished future years or unscheduled emergency closures.

Authoritative public sources frozen for this manifest:

- NYSE Holidays & Trading Hours:
  https://www.nyse.com/trade/hours-calendars
- NYSE 2026 Yearly Trading Calendar:
  https://www.nyse.com/publicdocs/nyse/ICE_NYSE_2026_Yearly_Trading_Calendar.pdf

Source facts used by 131-S:

- NYSE core equity trading session is 09:30-16:00 America/New_York;
- published full-market holidays for 2026, 2027, and 2028 are explicit;
- published early 13:00 closes are explicit and must not be inferred beyond the
  manifest:
  - 2026-11-27
  - 2026-12-24
  - 2027-11-26
  - 2028-07-03
  - 2028-11-24

Frozen public surface:

```text
NYSEPublishedRegularSessionAuthority
  .schedule_for(session_date: date)
      -> ReviewPaperSessionSchedule | None
```

Input and range authority:

- input must be exactly `datetime.date`, not `datetime.datetime`;
- supported years are exactly 2026, 2027, 2028;
- unsupported years fail closed with a dedicated error rather than extrapolating;
- Saturday/Sunday returns `None`;
- an explicit published full-market holiday returns `None`;
- an ordinary supported weekday returns one exact regular-session schedule;
- an explicit published early-close weekday returns one schedule closing 13:00
  America/New_York;
- all other supported sessions close 16:00 America/New_York;
- all sessions open 09:30 America/New_York;
- returned `ReviewPaperSessionSchedule` uses timezone-aware instants and relies
  on `ZoneInfo("America/New_York")` for DST rather than fixed offsets.

Frozen manifest identity:

```text
source_name = NYSE
source_scope = NYSE core equity regular session
manifest_version = nyse-published-regular-sessions-2026-2028/v1
supported_years = (2026, 2027, 2028)
source_as_of = 2026-10-04
```

The explicit full-market closure manifest is:

```text
2026:
  01-01, 01-19, 02-16, 04-03, 05-25,
  06-19, 07-03, 09-07, 11-26, 12-25

2027:
  01-01, 01-18, 02-15, 03-26, 05-31,
  06-18, 07-05, 09-06, 11-25, 12-24

2028:
  01-17, 02-21, 04-14, 05-29, 06-19,
  07-04, 09-04, 11-23, 12-25
```

Note that 2028-01-01 falls on Saturday and NYSE publishes no observed New Year's
closure for that holiday; the authority must not manufacture one.

131-S is static/versioned source authority only. It must perform no system-clock
read, web/network access, filesystem access, Robinhood/MCP/OAuth call, store
access, quote acquisition, risk evaluation, execution, environment/config read,
subprocess, retry, polling, scheduler, or sleep.

It must not modify `NYSEMarketCalendar`. That existing date-only calendar
retains its historical 1998-2100 contract; 131-S is a separate bounded,
published intraday authority intended to feed 131-M.

A future manifest refresh is an explicit source change requiring review and
certification. If NYSE changes a published holiday/early-close schedule, the
checked-in manifest must be updated; runtime network discovery is intentionally
out of scope.

Accepted source-only checkpoint:

```text
arch131-nyse-published-regular-session-authority
preflight=None
execute=None
```

It is registered after the two 131-R checkpoints in the side-foundation
optimized batch.

#### 131-S accepted source/certification — 2026-10-04

```text
BRANCH feature/robinhood-review-paper-side-foundation
PARENT 6638676c6ee4abb804903cb13396d9f807d78d34
HEAD   69327a7d5fbea7499329902ff96fd98e77a62591
TREE   8e39547005c320387ef231c8dfd5e914d2f02322
CI     #176 / 37235257282 SUCCESS

arch131-nyse-published-regular-session-authority
preflight=None
execute=None
```

131-S source was accepted at its own HEAD above. Final broad supported-product
certification subsequently ran on descendant Architecture 132-R1 HEAD
`91cafa03f9244523fc45df0716427402028257a7`, tree
`cb044a9014132b4e73310e19da5dfeba0fd89c3b`. That descendant contains unchanged
accepted 131-S executable source, so this one accepted FULL-supported
certification also closes 131-S. No standalone second certification was
required.

The descendant FULL-supported certification passed 3,694 cases across 113
supported modules (broad-1: 55 modules / 1,985 passed; broad-2: 58 modules /
1,709 passed), with zero skipped, failed, or error cases, wall 201.655 s,
`ARCH132_R1_FULL_CERTIFICATION_EXIT=0`, and
`ARCH132_R1_FULL_CERTIFICATION=PASS`. Source-gate CI for the descendant was
#178 / 37238601866 SUCCESS; its worktree/index remained clean.

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-a1860dc18fac474ba2fd9e163eaba684
```

The certified tier topology and complete 132-R1 record are maintained in
[Architecture 132](132-tiered-certification-profiles.md).

Production/live real-money placement remains **NO-GO**. Certification does not
authorize provider/broker effects. 131-Q PREPARE remains a protected read-only
provider boundary requiring fresh explicit authorization. 131-Q EXECUTE remains
a separate protected boundary requiring fresh explicit authorization after
accepted PREPARE. `READY_TO_PROCEED` is never execution authorization.
131-S adds schedule authority only, not provider/execution authority; 132-R1 is
test/workflow infrastructure only. The protected operational sequence remains
separate and unchanged; this closeout grants no new authority.

#### 131-T — explicit-date published-session PREPARE binding

**CERTIFIED.** 131-T removes manual `ReviewPaperSessionSchedule` construction
from the supervised PREPARE/qualification path while preserving explicit,
fail-closed temporal authority.

Accepted source identity:

```text
BRANCH  feature/robinhood-review-paper-side-foundation
PARENT  460a2be87905f024022a8630a4575f1080a6ec7f
HEAD    32c3bd41c6a48c24f7df5942eb082233a3624626
TREE    a8a35bb503ba3eea71cc175c01e6edc21393639a
CI      #182 / 37241669446 SUCCESS
```

Accepted composition:

```text
explicit caller session_date
        ↓
accepted 131-S NYSEPublishedRegularSessionAuthority exactly once
        ↓
exact canonical ReviewPaperSessionSchedule
        ↓
accepted 131-Q PREPARE / 131-R PREPARE qualification exactly once
```

The caller still supplies one exact `datetime.date`; 131-T never derives today
from the system clock, environment, provider, filesystem, or network. Unsupported
years propagate the accepted 131-S unsupported-year error; weekends and
published holidays fail as `ReviewPaperPublishedNonSessionDateError`. Invalid
resolution occurs before provider, store, evidence, PREPARE, or qualification
activity.

The accepted wrappers preserve every non-schedule caller object/value exactly,
preserve the exact 131-S schedule object, and return the exact delegate result.
They add no EXECUTE/pipeline/order path, retry, polling, scheduler, provider
calendar, direct transport, or added clock authority.

The provider-free PREPARE verifier now independently resolves the evidence
`session_date` through accepted 131-S and requires exact canonical
`opens_at`/`closes_at`. Unsupported years, weekends/holidays, ordinary-session
time drift, and early-close drift fail before durable-store reconciliation. The
existing `arch131-q-prepare-qualification/v1` evidence schema is unchanged.

Accepted checkpoint:

```text
arch131-robinhood-published-session-prepare
preflight=None
execute=None
```

It is registered exactly once immediately after 131-S in the 30-participant
source-gate batch.

Focused implementation verification passed 1,839 requested cases plus 2
delegate-failure regressions. Final ROBINHOOD certification on the exact source
tree passed 2,941/2,941 cases across 41 selected modules with zero skips,
failures, or errors in 173.193 seconds.

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-ec2be1768b7646eba09923bfba8bb98d
```

Current profile discovery is FULL 114 / ROBINHOOD 41 / LEGACY 204 / EXHAUSTIVE
318; the frozen 132-R1 minimum baselines remain 113/40.

##### Next protected operational sequence

No additional source milestone is required before qualification. Continue the
already-frozen sequence:

1. first live 131-L qualification on
   `feature/robinhood-review-paper-mode`;
2. separately authorize a bounded 131-Q PREPARE qualification using the accepted
   131-T explicit-date schedule composition;
3. after PREPARE evidence is independently accepted, separately authorize one
   131-Q EXECUTE qualification.

The current 131-L remote branch head
`909d51ce0c8418295d52e050557e49cfe8d8ee41` is a one-commit docs-only
descendant of accepted executable source
`97ab6b89931c105726944dc9609a9e0de062bac6`; no executable file differs across
that compare. Provider-free source/worktree readiness checks are safe, but the
first live 131-L request remains protected and requires fresh explicit
authorization. PREPARE and EXECUTE remain separate protected boundaries.
Production/live real-money placement remains **NO-GO**.

#### 131-U — source-owned PREPARE transport composition

**CERTIFIED.** 131-U removes the remaining ad-hoc transport/OAuth composition
from protected 131-Q PREPARE while adding no PREPARE authorization and no
EXECUTE capability.

Accepted source identity:

```text
BRANCH  feature/robinhood-review-paper-side-foundation
PARENT  b3cd29c04769c698fae9936fc165dff8768826a9
HEAD    8f793242b3ff00987376d4a27c9ae702cc8de6f5
TREE    6dce3f6e1fc7127674a20fc10af59f643f812abc
CI      #185 / 37245733735 SUCCESS
```

Accepted public boundary:

```text
run_robinhood_published_session_prepare_qualification(
    *,
    session_date: date,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
    expected_source_head: str,
    expected_source_tree: str,
    evidence_path: Path,
    redirect_uri: str,
) -> ReviewPaperSupervisedPreparation
```

Accepted composition:

```text
exact caller inputs
-> create_windows_robinhood_oauth_factory(
       redirect_uri=redirect_uri,
       browser_opener=<sanitized fail-closed blocker>,
   ) exactly once
-> RobinhoodMcpStreamableHttpTransport(oauth_factory) exactly once
-> RobinhoodReviewReadAdapter(transport) exactly once
-> accepted 131-T qualification wrapper exactly once
-> return exact delegated preparation
```

Construction of the OAuth factory, transport, and adapter is inert and performs
no credential read, authentication, callback listener startup, browser open,
MCP request, or Robinhood request. Interactive browser authorization is blocked
and does not create retry authority.

Fake end-to-end tests prove the reachable PREPARE path uses exactly one accepted
`get_equity_quotes` request and zero `get_accounts`, `get_equity_orders`,
`review_equity_order`, mutation, EXECUTE, 131-L pipeline, retry, polling, or
scheduler capability. Evidence remains PREPARE-only with
`execute_invoked=false` and `pipeline_result_present=false`.

Accepted checkpoint:

```text
arch131-robinhood-published-prepare-operator
preflight=None
execute=None
```

It is registered exactly once immediately after 131-T in the 31-participant
source-gate batch.

Final ROBINHOOD certification on the exact accepted source tree passed
3,054/3,054 cases across 42 selected modules, with zero skips/failures/errors,
in 184.225 seconds.

Evidence:

```text
F:\AI\temp\pytest\certification-evidence-604e559c475f47eabf7e708f9150eba4
```

Current profile discovery is FULL 115 / ROBINHOOD 42 / LEGACY 204 / EXHAUSTIVE
319; frozen Architecture 132-R1 minimum baselines remain 113/40.

##### Safe-side progression status after 131-U

At 131-U closeout no further source milestone was needed. The first live
PREPARE later exposed the process-lifetime gap addressed by the 131-V contract
below; 131-U itself remains PREPARE-only.

Continue only the already-frozen protected sequence:

1. first live 131-L qualification on the frozen
   `feature/robinhood-review-paper-mode` branch;
2. provider-free 131-LQ reconciliation and evidence acceptance;
3. separately authorize one 131-Q PREPARE qualification through accepted
   131-U;
4. after PREPARE acceptance, separately authorize one 131-Q EXECUTE
   qualification.

Repository/worktree identity checks and evidence/runbook review remain safe and
provider-free. Credential/provider access is a protected boundary.
`READY_TO_PROCEED` never authorizes EXECUTE, and production/live real-money
placement remains **NO-GO**.

### Live 131-L / 131-LQ qualification — ACCEPTED

The first authorized live 131-L durable-context forward-paper qualification is
accepted after provider-free reconciliation.

Qualified live identity:

```text
BRANCH feature/robinhood-review-paper-mode
HEAD   909d51ce0c8418295d52e050557e49cfe8d8ee41
TREE   a423709378b1add667c8753a6c477b98551db902
```

The executable 131-L source remains
`97ab6b89931c105726944dc9609a9e0de062bac6` /
`8942f72bebed58cb7536f227b866b7818b5ac513`.

Accepted live result:

```text
SPY BUY 2
qualification mark  769.650000
risk                RESIZED -> 1.000
reasons             MAX_POSITION_PERCENT, QUANTITY_INCREMENT

get_accounts        1
get_equity_orders   2
review_equity_order 1
get_equity_quotes   0

placement           0
cancellation        0
options mutation    0
crypto mutation     0
interactive reauth  0

final paper state:
  records           2
  cash              98457.100000000
  SPY quantity      2.000
  new fill          773.030000 @ 2026-10-05T16:04:31.957773+00:00
```

The first 131-LQ reconciliation exposed a verifier-schema defect only: the live
operator evidence correctly included the accepted four explicit mutation-safety
counters, all zero, while the older exact verifier dictionary omitted them.
The live qualification was not retried.

Provider-free correction:

```text
HEAD 1f0fbf6c19634b551701ff4f2038814f361887b9
TREE 6900e2244dcb9199674a37b84d7c74024f95ac96
CI   #187 / 37341614958 SUCCESS
```

The corrected verifier requires all four counters to equal zero and rejects any
nonzero value. ROBINHOOD certification passed 3,058/3,058 cases across 42
modules with zero skips/failures/errors. Provider-free reconciliation then
passed against the original already-produced evidence:

```text
ARCH131_LQ_VERIFICATION=PASS
records=2
cash=98457.100000000
position=2.000
order_id=22222222-131b-4000-8000-000000000001
fill_price=773.030000
fill_time=2026-10-05T16:04:31.957773+00:00
ARCH131_L_LIVE_AND_RECONCILIATION=PASS
```

#### Current protected sequence

Steps 1-2 of the previously frozen operational sequence are complete:

1. live 131-L qualification — **ACCEPTED**;
2. provider-free 131-LQ reconciliation — **ACCEPTED**;
3. next: one separately authorized 131-Q PREPARE qualification through accepted
   131-U;
4. only after PREPARE evidence is independently accepted, one separately
   authorized 131-Q EXECUTE qualification.

A PREPARE authorization permits only the accepted bounded quote-read/PREPARE
path. It does not authorize 131-L, `review_equity_order`, account/order-history
reads, placement/cancel/options/crypto mutation, retry, unattended scheduling,
or EXECUTE. `READY_TO_PROCEED` is never execution authorization. Production/live
real-money placement remains **NO-GO**.


### First live 131-Q PREPARE qualification — ACCEPTED

The first separately authorized live 131-Q PREPARE qualification through
certified 131-U is accepted.

```text
source HEAD/TREE:
114fca8e110c4e82d181aebafc30b0f689061265
4b307dc6df11cc6487b9c4518adeeb27970ba695

proposal:
11111111-131c-4000-8000-000000000001
SPY SELL 1.000

result:
READY_TO_PROCEED
APPROVED 1.000
quote_observed_at 2026-10-05T17:21:39.028389+00:00
quote_valid_until 2026-10-05T17:26:30.262285+00:00
execute_invoked false
pipeline_result_present false
durable bytes unchanged
provider-free verifier PASS
```

Evidence:

```text
F:\AI\temp\robinhood-131q-prepare-defbc565dc8d472fbfe0bc97522e9883\prepare-evidence.json
```

The MCP runtime printed `Session termination failed: 400` during transport
context teardown after the successful quote result. PREPARE returned normally,
the process exited 0, durable bytes remained unchanged, and independent
provider-free reconciliation passed. Record the warning as non-blocking
transport-close noise; it does not authorize retry.

The accepted preparation's quote deadline is authoritative. 131-Q requires
`execute_at <= quote_valid_until`; after
`2026-10-05T17:26:30.262285+00:00`, this preparation cannot enter 131-L. A
fresh provider-read PREPARE and fresh review are required before an EXECUTE
qualification can proceed.

Current protected progression:

1. first live 131-L + 131-LQ — **ACCEPTED**;
2. first live 131-Q PREPARE — **ACCEPTED**;
3. next goal: one 131-Q EXECUTE qualification;
4. because the accepted PREPARE has expired, first obtain a new separately
   authorized PREPARE with fresh evidence, then separately authorize EXECUTE
   while the new quote remains valid.

`READY_TO_PROCEED` remains evidence, never execution authorization.
Production/live real-money placement remains **NO-GO**.


### 131-V — in-process human-authorized EXECUTE qualification (source contract)

Frozen source-only checkpoint. The first accepted live PREPARE used an ad-hoc
one-shot Python process. Its exact `ReviewPaperSupervisedPreparation` disappeared
when that process exited, so it could not cross the separate human authorization
boundary required by accepted 131-Q EXECUTE. An expired PREPARE cannot be reused.
131-V keeps one fresh preparation alive in one qualification process; it never
serializes or reconstructs that object and never silently prepares again.

The qualification-only launcher is
`scripts/robinhood_supervised_qualification.py`. It bootstraps its own sibling
`src`, and admission proves the loaded project modules originate there. It
requires the caller's exact reviewed source branch/HEAD/tree, clean tracked/index
state, exact origin URL and live remote HEAD, local remote tree, published
explicit-date NYSE session, default reviewed risk limits, and caller-pinned
BEFORE fingerprint. The launcher pins this operator store identity:

```text
F:\AI\temp\robinhood-131j-source-live-91b4bf7f665947f79a6a94fd44ecae39\paper.sqlite
```

An appended `2`, a missing store, different path, altered historical fingerprint,
wrong balance, existing output, output overlap, or SQLite sidecar overlap stops
before PREPARE/provider access. Reusable source/domain code has no `F:` path.
The accepted two-record BEFORE state is starting cash 100000, current cash
98457.100000000, and SPY quantity 2.000. No third record/replay is admitted.

Frozen qualification identities and policy:

```text
caller proposal: 11111111-131c-4000-8000-000000000002 / SPY SELL 1.000
caller order:    22222222-131c-4000-8000-000000000001
execution:      MARKET / DAY
slippage:       0 basis points (preserve reviewed qualification policy)
commission:     0 (preserve reviewed qualification policy)
opening buffer / closing buffer / max quote age: 5 minutes each
redirect URI:   http://127.0.0.1:8765/callback
risk limits:    accepted default RiskLimits, trading enabled
```

131-V receives the caller's proposal/order identities and proposal timestamp;
it does not generate domain identities. Source/store/session/input admission
precedes inert store construction; full-column fingerprints must remain equal
through that construction. All three evidence outputs must be absolute, distinct,
fresh, outside the worktree, and have existing parent directories. The EXECUTE
output is reserved with exclusive creation before PREPARE. Existing output bytes
are preserved. PREPARE and underlying operator retain their accepted exclusive
publication. Failed evidence never grants a retry or an automatic cleanup.

Frozen sequence:

```text
provider-free admission
-> accepted source-owned 131-U PREPARE exactly once
-> accepted independent provider-free 131-R PREPARE verifier exactly once
-> require exact READY_TO_PROCEED / APPROVED SELL 1.000 / two-record BEFORE
-> hash canonical sanitized challenge material
-> emit one compact authorization-request JSON record, flush
-> exactly one blocking human terminal stdin.read()
-> require exact challenge-bound token frame, no retry
-> record authorization acceptance instant
-> construct explicit MARKET/DAY instruction after acceptance
-> accepted 131-Q EXECUTE once, passing the exact preparation object by identity
-> sanitized EXECUTE evidence
-> independent provider-free reconciliation
-> exit
```

The SHA-256 challenge covers canonical UTF-8 JSON (sorted keys, compact
separators, Unicode preserved): schema, source HEAD/tree, proposal/order UUIDs,
exact PREPARE evidence digest and resolved path, quote observation/deadline,
risk outcome/approved quantity, and exact execution configuration. Configuration
binds source branch/HEAD/tree, resolved store/operator evidence paths,
MARKET/DAY, slippage/commission, redirect-URI digest, every risk-limit field,
session buffers, quote age and trading-enabled flag. The request includes that
material, sanitized risk preview and durable BEFORE fingerprint for review.
`READY_TO_PROCEED` is never authorization.

The operator explicitly approved whole-frame stdin framing: type exactly
`AUTHORIZE 131-Q EXECUTE <challenge>`, press Enter, then press Ctrl+Z and Enter
on Windows to terminate that one read. Only that token followed by one newline
is accepted. Empty EOF, blank input, wrong challenge, whitespace, malformed
input, a second line, interrupted read, or read error stops without EXECUTE.
Redirected/nonterminal stdin is rejected before PREPARE. The process stays alive
while ChatGPT/operator reviews the request. There is no callback/reader/executor
injection API, file watch, polling, sleep, scheduler or retry loop. Token input
is never persisted; sanitized evidence stores the challenge and acceptance flag.
The PREPARE digest is stable around verification and reread after the pause;
the full durable fingerprint must still equal BEFORE before EXECUTE is invoked.

Accepted 131-Q alone remains authoritative for its execute clock, canonical
session admission, `execute_at <= quote_valid_until`, prepared/revalidated risk
context and decision equality, history drift, instruction ordering and exactly
one accepted 131-L invocation. 131-V calls no 131-L/J/I/H directly and reacquires
no quote. Source acceptance grants neither PREPARE provider access nor EXECUTE
authority. Each launch requires fresh separate PREPARE authorization; EXECUTE
requires the later challenge response while the same preparation remains fresh.

The closed `arch131-q-execute-qualification/v1` evidence records source and
proposal/order identities, PREPARE digest/path, challenge and authorization time,
instruction time, quote observation/deadline, exact configuration, execute
admission, prepared/revalidated sanitized risk material, full-column durable
BEFORE/AFTER fingerprint/count, exact underlying returned operator evidence
and its file digest/path, four mutation counters, interactive reauthorization
count, PREPARE/verifier/stdin/EXECUTE counts, EXECUTE/131-L invocation state,
zero retry count, and final status. Provider output/logs/warnings are discarded,
and no arbitrary exception, traceback, OAuth material, account identifier,
header, redirect secret or raw provider payload is serialized.

A failure before EXECUTE records `STOP` and no 131-L invocation. An exception
from EXECUTE records `INDETERMINATE` and `forward_cycle_invoked=null`, because
accepted 131-Q may raise either before or after 131-L. No downstream invocation
is inferred from the exception. Unavailable reauthorization/evidence remains
null. A returned operator FAIL remains FAIL. Only independently reconciled PASS
certifies qualification; STOP/FAIL/INDETERMINATE never authorize retry or replay.

`robinhood_execute_qualification_verifier` imports no transport/OAuth/executor
boundary, opens SQLite only with URI `mode=ro`, and writes nothing. It separately
reconstructs challenge material, strictly validates every evidence/nested schema,
source/proposal/order/configuration identity, PREPARE digest/path, published
session and timestamps (observation <= acceptance <= instruction <= execute <=
deadline), prepared/revalidated risk, counters and operator linkage. It removes
only the exact qualification row from its in-memory snapshot and independently
fingerprints the remaining two records against caller-pinned BEFORE and both
PREPARE fingerprints. AFTER must match the current full database. Exactly one
new SELL record must match the frozen proposal/order/risk/MARKET/DAY material,
deterministic trade/fill identities, zero commission/slippage and bid-price/time
fill. Operator evidence must prove one review, no quote reacquisition, zero
placement/cancel/options/crypto, zero interactive reauthorization and no replay.
The review-paper package's performance exports are lazy solely to prevent
session/verifier imports from indirectly loading MCP transport; public exported
objects retain their original identities.

One new source-only checkpoint covers composition, launcher, verifier and
provider-free package admission:

```text
arch131-robinhood-supervised-qualification
preflight=None
execute=None
```

It follows 131-U once in the 32-participant source-gate batch, pinning complete
ASTs and source-only registration. New tests remain under
`tests/test_robinhood_*.py`, automatically current-supported/Robinhood owned.
Old checkpoint registrations and authority-source pins are unchanged; their
shared batch digest advances only for the appended participant. Source tests
use doubles/fake quotes and fixture SQLite only. No real provider/OAuth call,
protected store write or real brokerage effect is authorized during development.

#### Qualification runbook (after source acceptance and ROBINHOOD certification)

Replace the former one-shot PREPARE here-doc with this source-owned launcher.
ChatGPT must freeze the exact accepted source identities and BEFORE digest from
provider-free review first. The variables below are explicit reviewed operator
inputs, not authority inferred from the current checkout. The source launcher
must be invoked only after separate PREPARE authorization. Existing/expired
PREPARE evidence cannot be loaded as a new preparation.

```powershell
$qualificationRoot = 'F:\AI\worktrees\ai-trading-bot-robinhood-side-foundation'
$qualificationPython = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
$qualificationStore = 'F:\AI\temp\robinhood-131j-source-live-91b4bf7f665947f79a6a94fd44ecae39\paper.sqlite'
# Fill these only from independently reviewed admission/source material:
$qualificationHead = '<accepted HEAD>'
$qualificationTree = '<accepted TREE>'
$qualificationBeforeSha256 = '<accepted two-record BEFORE SHA-256>'
$qualificationSessionDate = '<explicit published session YYYY-MM-DD>'
$qualificationProposalCreatedAt = '<explicit UTC proposal timestamp>'
$qualificationPrepareEvidence = '<fresh absolute PREPARE evidence path>'
$qualificationExecuteEvidence = '<fresh distinct absolute EXECUTE evidence path>'
$qualificationOperatorEvidence = '<fresh distinct absolute operator evidence path>'

& $qualificationPython "$qualificationRoot\scripts\robinhood_supervised_qualification.py" `
  --session-date $qualificationSessionDate `
  --store $qualificationStore `
  --expected-before-sha256 $qualificationBeforeSha256 `
  --proposal-id '11111111-131c-4000-8000-000000000002' `
  --order-id '22222222-131c-4000-8000-000000000001' `
  --proposal-created-at $qualificationProposalCreatedAt `
  --expected-branch 'feature/robinhood-review-paper-side-foundation' `
  --expected-head $qualificationHead --expected-tree $qualificationTree `
  --prepare-evidence $qualificationPrepareEvidence `
  --execute-evidence $qualificationExecuteEvidence `
  --operator-evidence $qualificationOperatorEvidence `
  --redirect-uri 'http://127.0.0.1:8765/callback' `
  --slippage-basis-points 0 --commission 0
```

Leave the process alive at AUTHORIZATION_REQUIRED. Review the exact printed
challenge/source/risk/deadline/configuration before any EXECUTE authorization.
After fresh explicit approval, type the exact token, Enter, then Ctrl+Z and
Enter. A STOP is terminal. Do not rerun without a new reviewed checkpoint and
new PREPARE authorization. Real-money trading remains NO-GO.

PROJECT_STATUS and AI_TRADING_BOT_HANDOFF final closeout is deliberately deferred
until ChatGPT exact source acceptance and the chosen certification gate pass.

## D10 disposition

D10 remains frozen historical infrastructure with its scheduler disabled.
Architecture 131 does not restart or reuse the failed D10 unattended soak.
