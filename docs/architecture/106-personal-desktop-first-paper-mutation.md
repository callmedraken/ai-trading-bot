# Architecture 106 — Personal-Desktop First Paper Mutation

Status: frozen PD2D2-A design checkpoint; documentation only; no production
effect or mutation authorization.

## Purpose

PD2D2 defines one durable first Paper-v2 operation for the already-qualified,
frozen operation below. It does not create reusable runtime authority, grant a
second invocation, or authorize any later paper execution. It does not
authorize broker, provider, scheduler, credential, account, ACL, LSA, KSP, or
live-trading effects.

The staged checkpoint sequence is:

```text
PD2D2-A  architecture plus validation/evidence freeze only (this checkpoint)
PD2D2-B  zero-semantic-input one-shot harness; source-only tests; gate false
PD2D2-C  separate minimal source change enabling only the supervised gate
PD2D2-D  fresh explicit approval, then exactly one Trading-account invocation
PD2D2-E  separate source re-disable, then reviewed read-only reconciliation
```

PD2D2-D is never automatic.

## Fixed operation identity

The only operation in scope is:

```text
paper_account_id:        9415cd7b-bf36-5fba-bd58-a0f99119dc21
prior checkpoint ID:    1832a2b5-8b63-501a-8f7d-f1722c32307b
selection_id:            36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
selected_snapshot_id:    eba46838-44ae-5bec-97bf-98c6639ae6a7
seed_id:                 5dc95e10-ba22-5b91-94b2-0d851aa8e2d7
caller idempotency UUID: c762ad22-8d10-43d7-a38b-7d95e730c5ea
request_id:              bc0c3aa7-09a0-5534-83bf-0acdf649a2a0
plan_id:                 78292abe-6d6c-5ddf-8ffb-46eb8a914fdb
plan SHA-256:            7f62c90df051f5c4998cc3303b7a97dfb80294dfd743662c2f9930422cb83666
plan byte length:        6199
operation_id:            307f769a-f09a-539d-b12d-3fb51b973809
application_id:          78a1bae8-51ac-5bf0-b159-500768c758fc
```

The prior checkpoint is the published GENESIS and the PD2D1 terminal at
qualification time. These identities are immutable. A mismatch is STOP
evidence; it is not a reason to replan or issue a new idempotency UUID.

## Frozen pure inputs

PD2D2 preserves the complete PD2D1-F1/F2 profile without semantic CLI knobs:

```text
strategy_config:
  short_window: 3
  long_window: 5
  desired_quantity: Decimal("1")

timing:
  planning_at:  2026-08-29T09:46:43.769105+00:00
  submitted_at: 2026-08-31T13:30:00+00:00
  filled_at:    2026-08-31T13:30:00+00:00

open_reference:
  symbol: SPY
  session: 2026-08-31
  caller_asserted_open_reference_price: Decimal("767.33")

metadata: ()
historical_cycle_configuration_payloads: ()
```

The exact strategy-history seed is the canonical 1060-byte artifact with
SHA-256
`40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64`
and seed ID `5dc95e10-ba22-5b91-94b2-0d851aa8e2d7`.

The exact policies remain:

```text
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

proposal_confidence: None

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

trading_enabled: True
```

The harness must embed these source-owned constants and accept no positional or
optional semantic input. It must not use current time, current market data, an
environment override, or a replacement artifact.

## Production execution composition

PD2D2 uses only the existing public boundary:

```text
execute_supervised_personal_desktop_paper_operation(...)
```

That boundary must continue to:

1. validate genuine C1 production authority and genuine P2 selected-call-#6
   provenance;
2. construct genuine PD2B3 preparation;
3. acquire the same PD2A account-scoped mutex;
4. reread and revalidate Paper-v2 after the lock;
5. rebuild and byte-for-byte replay the exact P1 plan;
6. construct the exact intent and verified execution inputs;
7. require the fixed production operation root
   `F:\AITradingBot\Paper-v2\runtime`;
8. call the existing `execute_paper_operation_once` boundary exactly once while
   the same preparation/mutex scope is active; and
9. reconcile the returned operation and application IDs before exposing the
   sanitized result.

No second executor, detached preparation, raw-root API, retry loop, or recovery
mode is permitted.

## Gate authority

The only execution effect-enablement mechanism is the source-owned constant:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
```

PD2D2-B leaves it `False`. PD2D2-C may change exactly that constant from
`False` to `True` in a separate, minimally reviewed source checkpoint. No
environment variable, `--force` option, registry value, configuration file,
operator token, mutable runtime switch, alternate executor, or recovery switch
may enable execution.

The publisher and recovery gates remain `False` throughout:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
```

## Pre-execution state

The recorded PD2D1 `READY` result is required evidence for reviewing PD2D2-B/C,
but it is point-in-time evidence only. It is not passed to the executor and is
not reusable execution authority.

At the one authorized invocation, the PD2C path must obtain genuine C1 and P2
state again, acquire the mutex, reread Paper-v2, replay P1, and construct the
fixed operation from scratch. The Architecture-67 executor's own initial
inspection must observe the current operation as exact `PENDING` with diagnostic
`PENDING`. Any drift or uncertainty stops the invocation.

## Expected first-run result and durable names

For the qualified clean `PENDING` operation, the strongest normal success
condition exposed by the existing contracts is:

```text
operation_id:                  307f769a-f09a-539d-b12d-3fb51b973809
application_id:                78a1bae8-51ac-5bf0-b159-500768c758fc
execution_classification:      COMPLETED
diagnostic_code:               COMPLETED
cycle_result_id:               non-null UUID
successor_checkpoint_id:       non-null UUID
transition_evidence_produced:  True
receipt_evidence_produced:     True
executor_called:               True
```

The following production paths and names are knowable before execution and are
frozen:

```text
operation root:
F:\AITradingBot\Paper-v2\runtime

transition staging directory:
F:\AITradingBot\Paper-v2\runtime\.paper-account-transition-78a1bae8-51ac-5bf0-b159-500768c758fc.staging

transition final directory:
F:\AITradingBot\Paper-v2\runtime\paper-account-transition-78a1bae8-51ac-5bf0-b159-500768c758fc

receipt staging directory:
F:\AITradingBot\Paper-v2\runtime\paper-operations\.paper-operation-307f769a-f09a-539d-b12d-3fb51b973809.staging

receipt final directory:
F:\AITradingBot\Paper-v2\runtime\paper-operations\paper-operation-307f769a-f09a-539d-b12d-3fb51b973809

receipt final file:
F:\AITradingBot\Paper-v2\runtime\paper-operations\paper-operation-307f769a-f09a-539d-b12d-3fb51b973809\paper-operation-receipt-307f769a-f09a-539d-b12d-3fb51b973809.json
```

The transition directory's two final filenames are deterministically shaped as
follows, but their UUID components are not known until the real cycle produces
the corresponding result and successor:

```text
checkpointed-paper-cycle-report-<cycle_result_id>.json
paper-account-checkpoint-<successor_checkpoint_id>.json
```

PD2D2 must not invent those UUIDs before execution.

## One-invocation result policy

Exactly one process invocation is permitted by a future fresh PD2D2-D
authorization. The only intended success is the complete result above after an
initial clean `PENDING/PENDING` inspection.

Every other result is STOP evidence, including `BLOCKED`, `CONFLICTING`,
`ALREADY_APPLIED`, `EXECUTION_FAILED`, `RECEIPT_RECOVERED`, wrong or null
identity/evidence fields, an exception, process interruption, missing or
ambiguous output, or a nonzero harness exit. `RECEIPT_RECOVERED` is not a normal
first-run result because this invocation is required to begin from clean
`PENDING` state.

There is no automatic or operator-initiated retry under the same authorization.

## Crash and interruption contract

If the process is interrupted, the shell disappears, output is lost, or the
result is ambiguous:

```text
DO NOT rerun.
DO NOT delete staging or final objects.
DO NOT repair or rename anything manually.
DO NOT invoke recovery.
```

First close the effect window through the separate reviewed PD2D2-E source
checkpoint that restores the supervised-execution gate to `False`. Only then
perform read-only account/operation reconciliation to distinguish:

```text
nothing committed
transition staging remains
finalized transition exists without a receipt
receipt exists
operation is already applied
conflicting, invalid, or otherwise unsafe state
```

Any recovery or further invocation requires new explicit architecture/source
review and new user authorization. Architecture 67's existing recovery
capability is not authorization to call it.

## Post-success gate closure

Even after clean success, gate-enabled source is not the normal branch state.
PD2D2-E must be a separately reviewed source change that returns only:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

The gate must be closed before post-mutation reconciliation and before any PD3
or unattended work.

## Post-mutation readback

After source re-disablement, a reviewed read-only harness must use existing
genuine readers, inspectors, and verifiers only. It must establish:

- genuine C1 evidence for the exact non-elevated Trading principal;
- a genuine Paper-v2 account reread using
  `read_personal_desktop_paper_account(...)`;
- the original GENESIS checkpoint remains a valid ancestor;
- normal success advanced the account terminal by exactly one lineage edge;
- the returned cycle-result and successor-checkpoint IDs match the committed
  report, successor checkpoint, and verified lineage;
- the exact Architecture-67 operation inspection reports the frozen operation
  as `ALREADY_APPLIED` (or, after an interrupted/abnormal result, the exact
  fail-closed state under review);
- the exact receipt is read and validated through the existing receipt and
  lineage verification contracts;
- no transition or receipt staging object remains after normal success;
- exactly one transition for the frozen application and exactly one receipt for
  the frozen operation exist, with no unexpected second transition/receipt;
- all three source effect gates are `False` again.

The readback may report evidence but may not delete, repair, recover, rename, or
reinterpret durable state.

## Authorization barrier

**PD2D2 architecture acceptance is not source-enablement authorization.**

**PD2D2 source acceptance is not mutation authorization.**

**Review of gate-enabled source is not mutation authorization.**

The single Trading-account invocation requires fresh explicit user approval
immediately before it is run. No earlier qualification, review, commit, push,
or test result crosses that barrier.
