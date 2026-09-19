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

## Frozen offline market evidence

PD2D1-F2 freezes the two formerly open market-evidence inputs. Their complete
source and provenance record is
`docs/validation/pd2d1-first-cycle-market-data-evidence.md`.

```text
strategy-history artifact:
  path: docs/validation/evidence/pd2d1-spy-strategy-history-seed-2026-08-28.json
  seed_id: 5dc95e10-ba22-5b91-94b2-0d851aa8e2d7
  SHA-256: 40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64
  byte length: 1060
  source_id: stockanalysis-tiingo-spy-daily-2026-08-v1

next-session open reference:
  symbol: SPY
  session: 2026-08-31
  caller_asserted_open_reference_price: Decimal("767.33")
```

Both values are non-authoritative offline historical evidence. They grant no C3
authority, and the `2026-08-28` target bar remains the genuine selected C3
snapshot bar. This freeze does not claim that PD2D1 real-host qualification has
occurred and does not authorize a provider or broker call.

## Authorization boundary

This is a documentation-only pure-input freeze. It does not invoke C1 or P2,
acquire the production mutex, read or mutate Paper-v2, call a provider or
broker, enable an effect gate, or start PD2D2. PD2D2 remains **NOT AUTHORIZED**.
