# Architecture 131 — Robinhood Manual-Approval Paper Trading

## Status

Source-design checkpoint for replacing the local D10 unattended paper-execution
host with a third-party AI decision system connected to Robinhood's Trading MCP.

This architecture does **not** enable live trading. Robinhood Trade approvals
must remain ON in paper mode. A Robinhood approval request is treated only as an
externally visible proposal ticket. The bot's own virtual account remains the
authoritative simulated portfolio.

## Goal

Reuse the existing research, strategy, backtesting, TradeProposal,
deterministic RiskManager, OrderEngine, and PaperLedger while replacing the
local standalone broker-paper host with this flow:

```text
research / third-party AI
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
Robinhood Trading MCP
  Trade approvals = ON
        |
        v
pending approval request
        |
        +--> durable synthetic paper fill
        |
        +--> decline approval
        |
        v
virtual paper portfolio / P&L history
```

Robinhood is the proposal, market-data, and later execution transport. It is not
the strategy engine, risk engine, or paper-account ledger.

## Safety boundary

Paper mode must prove Robinhood Trade approvals are enabled before any
order-proposal tool is called.

The intended external sequence is:

1. `get_trade_approval_setting` proves approvals ON.
2. AI produces one TradeProposal.
3. deterministic RiskManager returns APPROVED or RESIZED.
4. local OrderEngine creates the broker-independent order.
5. optional `review_equity_order` performs Robinhood pre-trade review.
6. `place_equity_order` is called only while approvals are ON, creating a
   Robinhood approval request rather than a placed order.
7. `get_trade_approvals` must identify exactly one matching pending request.
8. a post-proposal equity quote is captured.
9. the approval and synthetic fill are durably committed to the local paper
   ledger.
10. only after durable local commit, `decline_trade_approval` is called.
11. `get_trade_approvals` confirms the request is no longer pending.

The bot must never call an approval/placement action in paper mode when the
approval setting is OFF or unknown.

## Why decline after recording

Leaving proposed orders pending creates an avoidable chance that a human could
later approve an old paper signal and turn it into a real order.

Therefore the normal terminal paper-mode state is:

```text
durable paper fill = recorded
Robinhood approval = declined
real Robinhood order = none
```

If the durable paper record exists but decline confirmation is unavailable, the
record remains `PENDING_DECLINE` and **all later order proposals stop** until
the approval is reconciled. There is no blind retry that could hide ambiguous
external state.

## Virtual account

Paper mode owns an independent virtual account, defaulting to $10,000.

Risk evaluation uses:

- virtual cash,
- virtual positions,
- virtual exposure,
- current market price.

It does not use the real MCP account buying power or real positions as its
paper-risk state.

Robinhood account data may still be read as research context, but it cannot
silently alter the simulated portfolio.

## Initial fill policy

Architecture 131 phase A supports long-only equity/ETF MARKET orders only.

For a quote captured after the Robinhood approval request appears:

```text
BUY  fill = ask * (1 + slippage_bps / 10000)
SELL fill = bid * (1 - slippage_bps / 10000)
```

The default simulated commission is zero. Slippage is explicit and persisted.

The quote timestamp must not precede the approval timestamp.

Limit, stop, options, crypto, margin, shorts, and leveraged products remain out
of scope for the initial paper adapter.

## Durable history

Each Robinhood approval request is an idempotency key.

One durable record retains:

- Robinhood approval ID,
- local proposal ID,
- local order ID,
- symbol and side,
- AI proposal reason and confidence,
- desired and risk-approved quantity,
- risk outcome and reason codes,
- order type and time-in-force,
- approval timestamp,
- post-proposal bid/ask quote and quote timestamp,
- simulated slippage and commission,
- deterministic fill ID and fill price,
- paper-record ID,
- approval-decline state and confirmation timestamp.

Duplicate observation of the same exact approval is idempotent. Reuse of one
approval ID with different material is a hard conflict.

The paper ledger is reconstructed from durable simulated fills at startup.
Current P&L can therefore be valued from fresh market prices without trusting
process memory.

## Failure semantics

Before durable paper commit:

- ambiguity means no synthetic fill is recorded.

After durable paper commit but before decline confirmation:

- paper history is retained,
- approval state is `PENDING_DECLINE`,
- later proposal creation is blocked until read-only reconciliation.

If Robinhood reports that a proposal was actually approved/placed unexpectedly,
paper mode stops. It must not reinterpret a real order as a paper fill.

## Current checkpoint

Registered source gate:

```text
arch131-robinhood-approval-paper
```

Phase A contains no MCP/network capability. It implements only:

- immutable approval-paper models,
- deterministic synthetic MARKET fill policy,
- SQLite-backed durable history,
- idempotent replay,
- virtual PaperLedger reconstruction,
- decline-confirmation bookkeeping.

## Follow-on checkpoints

### 131-B — read-only Robinhood MCP adapter

Add external-agent connection and read-only wrappers for:

- `get_trade_approval_setting`
- `get_trade_approvals`
- `get_equity_quotes`
- account/tool capability discovery

No order proposal yet.

### 131-C — protected paper proposal/decline adapter

Add the reviewed paper-mode sequence:

- approvals-on proof,
- Robinhood proposal,
- exact pending-approval reconciliation,
- quote capture,
- durable paper commit,
- decline,
- decline confirmation.

This is an external-effect boundary even though it does not intentionally place
a real order, and it requires a separate reviewed authority contract.

### 131-D — performance tracking

Add periodic valuation snapshots and reports for:

- realized P&L,
- unrealized P&L,
- total return,
- drawdown,
- win/loss rate,
- trade-by-trade results,
- strategy/model attribution.

### 132 — third-party AI decision contract

Connect the selected external model to research and strategy tools while
preserving deterministic risk authority.

## D10 disposition

D10 remains frozen historical infrastructure. Its scheduler stays disabled.
Architecture 131 does not restart, resume, extend, or reuse the failed D10 soak.
