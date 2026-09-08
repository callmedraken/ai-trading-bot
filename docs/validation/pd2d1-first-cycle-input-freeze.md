# PD2D1 First Supervised-Cycle Pure-Input Freeze

## Status and scope

This checkpoint records the architecture-owned pure, non-market-data input
profile for the first supervised-cycle qualification. PD2D1 source is accepted
and verified, and RH0 planning is accepted. This record does not claim that the
PD2D1 real-host qualification has occurred, does not authorize PD2D2, and grants
no authority to enable an effect gate or mutate Paper-v2.

The `3/5/1` moving-average strategy configuration below is a first-cycle
qualification profile only. It is not a performance claim, optimizer result,
research winner, or live-strategy authorization.

## Frozen qualification profile

The first-cycle qualification uses exactly:

```text
strategy_config:
  short_window: 3
  long_window: 5
  desired_quantity: Decimal("1")

caller_idempotency_key:
  c762ad22-8d10-43d7-a38b-7d95e730c5ea

timing:
  planning_at:  2026-08-29T09:46:43.769105+00:00
  submitted_at: 2026-08-31T13:30:00+00:00
  filled_at:    2026-08-31T13:30:00+00:00

RebalanceAssumptions:
  fixed_commission: Decimal("0")
  allow_fractional_quantities: False
  quantity_increment: Decimal("1")
  minimum_trade_notional: Decimal("0")
  minimum_trade_quantity: Decimal("1")
  target_weight_tolerance: Decimal("0")
  additional_execution_cash_buffer: Decimal("0")
  use_planned_sell_proceeds: False

PortfolioConstraints:
  minimum_cash_weight: Decimal("0.90")
  maximum_cash_weight: Decimal("1")
  maximum_position_weight: Decimal("0.10")
  maximum_one_way_rebalance_turnover: Decimal("0.10")
  minimum_position_weight: None
  long_only: True
  allow_leverage: False

RebalanceProposalPolicy:
  allow_partial_plans: False

proposal_confidence:
  None

RiskLimits:
  max_position_percent: Decimal("0.10")
  max_total_exposure_percent: Decimal("0.10")
  max_order_notional: Decimal("2500")
  max_new_position_percent: Decimal("0.10")
  minimum_cash_reserve_percent: Decimal("0.90")
  allow_fractional_shares: False
  fractional_increment: Decimal("1")
  allow_buying: True
  allow_selling: True
  estimated_commission: Decimal("0")

PortfolioRiskPolicy:
  allow_sell_proceeds_for_later_buys: False

PaperFillPolicy:
  slippage_basis_points: Decimal("0")
  fixed_commission: Decimal("0")

trading_enabled:
  True

metadata:
  ()

historical_cycle_configuration_payloads:
  ()
```

For `historical_cycle_configuration_payloads`, `()` is the frozen qualification
candidate for the currently expected GENESIS-only account. The later genuine
post-lock read must confirm that expectation. If durable state requires
historical configuration bytes, qualification must fail closed rather than
changing this input silently.

## Session and timing semantics

The selected C3 target session is `2026-08-28`. Its modeled next XNYS session is
`2026-08-31`, and `13:30 UTC` is `09:30 America/New_York` for that session. The
timestamps above are explicit pure inputs; no wall-clock value participates in
planning, identity, qualification, or later replay.

PD2D1 and any eventually authorized PD2D2 execution must use the same caller
idempotency UUID and identical semantic planning inputs. PD2D2 must not silently
replan, substitute current time, change policy, or manufacture a new UUID.

## Deliberately not frozen evidence

Two evidence values remain deliberately **not frozen** by this checkpoint and
block a runnable real-host qualification.

1. The `strategy-history-seed/v1` artifact must contain the exact five
   consecutive XNYS sessions immediately before `2026-08-28`. A later evidence
   checkpoint must freeze its exact canonical bytes, SHA-256, byte length,
   offline source descriptor, and reviewed transport location.
2. The `CallerAssertedNextSessionOpenReference` price for SPY on `2026-08-31`
   must come from separately preserved and reviewed offline historical
   evidence. It must not be inferred from the selected close, fetched during
   this checkpoint, or copied from a test/example value.

Until both evidence values are separately preserved, reviewed, and frozen,
PD2D1 real-host qualification is not runnable. No provider call or broker call
is authorized to fill either gap.

## Authorization boundary

This is a documentation-only pure-input freeze. It does not invoke C1 or P2,
acquire the production mutex, read or mutate Paper-v2, call a provider or
broker, enable an effect gate, or start PD2D2. PD2D2 remains **NOT AUTHORIZED**.
