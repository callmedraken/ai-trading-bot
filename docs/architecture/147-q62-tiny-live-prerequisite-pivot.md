# Architecture 147 — Q62 tiny-live prerequisite pivot

Status: CURRENT prospective prototype design. L41R6 source is accepted and
integrated; Q62, L43, and Q63 remain NOT RUN. This document grants no provider,
broker, review, placement, cancellation, or FINAL_HOLDOUT authority.

## Why the pivot is required

L41R6 completed the intended static evidence path. It authenticated the official
Robinhood claims actually supported by public material and combined them with the
exact consumed L41 and L41R5 artifacts. The truthful result is seven PROVEN
facts, five BLOCKING_L42 facts, and one position-specific deferral.

The five blockers are:

- QUANTITY_INCREMENT;
- MINIMUM_QUANTITY;
- MAXIMUM_QUANTITY_OR_ABSENCE;
- BELOW_MINIMUM_FULL_CLOSE;
- RESIDUAL_FULL_OWNED_CLOSE.

They are not parser bugs. Robinhood's accepted public material does not establish
global MCP values/guarantees for them, and documentation silence cannot establish
absence of a maximum. The app Sell All path and fifth/sixth-decimal holding
precision do not prove an automated MCP residual close.

This crosses the current product pivot threshold. Do not build L41R7 or another
schema/prose/rule-evidence recovery around the same absent global facts.

## Non-regression

All historical/current predecessor evidence remains truthful and unchanged.

In particular, do not modify the meaning of:

- FactId / Classification / CapabilityReport;
- classify_capabilities;
- the accepted L41R6 seven/five/one result;
- consumed L41/L41R1-R5 artifacts;
- historical evaluate_q62_readiness;
- L40 exact ownership, budget, unknown-effect, and no-short constraints.

The successor is additive. A new prospective prototype capability admission and
Q62 evaluator own the relaxed prerequisite model. BLOCKING_L42 facts are not
renamed, reclassified, or silently treated as PROVEN.

## Prototype scope

The pivot applies only to the first explicitly armed tiny-live SPY trial.

Frozen limits remain:

- private single-user desktop;
- SPY only;
- BASE_MA35_50_V1;
- cash long only;
- no margin, short, options, crypto, provider fallback, or paper soak;
- regular-hours market operation;
- one entry intent only;
- at most $10 requested acquisition and no replenishing budget;
- no second entry after rejection, cancellation, partial fill, exit, restart, or
  date change;
- exact source/config/account/session/strategy identity;
- FINAL_HOLDOUT sealed.

The pivot is not P7 production maturity and does not authorize repeated
unattended live trading.

## Prototype capability adapter

Add a new typed current-product adapter, conceptually
TinyLivePrototypeCapabilityAdmission.

It accepts the exact independently accepted L41R6 composite identity only when:

1. the FactId inventory is exact and in source order;
2. the seven expected facts are PROVEN;
3. the five expected facts are BLOCKING_L42 with the accepted L41R6 rationale
   codes;
4. INSTANCE_REVIEW_REQUIRES_POSITION is the sole
   DEFER_TO_FIRST_OWNED_POSITION fact;
5. no additional/missing blocker or deferral exists;
6. consumed L41/L41R5 and official-binding identities match the accepted L41R6
   lineage;
7. the account fingerprint matches the Q62 readiness identity.

The adapter does not emit READY_FOR_L42 and does not mutate CapabilityReport.
It emits a separate prototype status such as ELIGIBLE_FOR_TINY_LIVE_Q62 or
BLOCKED.

## Why each global blocker is not a prototype prerequisite

### QUANTITY_INCREMENT / MINIMUM_QUANTITY

The bot does not invent a sell quantity before ownership exists. Entry remains a
dollar-based <=$10 order.

After a confirmed entry fill, factual reconciliation establishes the exact bot-
owned quantity and currently sellable broker quantity. Before any automated
sell placement, the bot must submit that exact proposed full-owned quantity to
Robinhood's accepted nonplacing review tool using the same material order
arguments intended for placement.

If review does not affirm the exact proposal, no sell placement occurs. The
prototype becomes MANUAL_CLOSE_REQUIRED and automated live trading remains
disabled.

Thus the prototype does not need a global pre-entry increment/minimum rule. It
needs exact-proposal acceptance after a real owned position exists.

### MAXIMUM_QUANTITY_OR_ABSENCE

The prototype imposes its own much smaller exposure bound: one <=$10 requested
acquisition. No inference is made that Robinhood has no maximum.

The specific full-owned sell proposal is reviewed before placement. A provider
rejection is a blocked/safe outcome, not permission to widen or retry.

### BELOW_MINIMUM_FULL_CLOSE / RESIDUAL_FULL_OWNED_CLOSE

The automated prototype does not claim these capabilities.

If an exact full-owned review or placement cannot close the position, or if a
sell is rejected, canceled, partially filled, produces a residual, or becomes
UNKNOWN, no blind replacement sell is created.

The durable state records the exact remaining owned quantity and transitions to
MANUAL_CLOSE_REQUIRED / trading disabled. The single trusted user may resolve
the tiny position manually through Robinhood. After manual resolution, a fresh
read-only reconciliation must prove the account position/order state before any
later live milestone.

The public app Sell All behavior is context for manual recovery only. It is not
MCP automated-close authority.

## Exact sell-review rule

The first owned-position review remains deferred until a genuine bot-owned
position exists.

Before automated exit placement:

- reconcile exact durable owned quantity from confirmed fills;
- corroborate current broker position and sellable quantity;
- require requested sell quantity > 0 and <= both exact owned remainder and
  broker-sellable quantity;
- use the exact full owned quantity; no round-up, guessed increment, dollar
  substitution, or adoption of manual shares;
- review side=sell, symbol=SPY, market order, regular-hours session and the same
  time-in-force/session arguments that placement would use;
- review is nonplacing evidence only;
- only a source-owned accepted review result may permit the corresponding
  placement;
- review rejection/malformed/unknown/warning state fails closed;
- placement may still reject; rejection does not restore entry or create retry
  authority.

The source implementation must define the accepted review response shape before
L43. Synthetic tests are not provider qualification; the first real exact-owned
review remains an L43 protected boundary.

## Partial/unknown outcomes

Existing exact ownership and MAY_HAVE_OCCURRED rules remain.

A partial entry owns only confirmed fill quantity but consumes the full entry
reservation. The prototype may proceed to exact-owned review only after the
entry order is terminal and reconciliation is factual.

A partial/unknown exit never creates an automatic replacement order. Preserve
the exact residual and enter MANUAL_CLOSE_REQUIRED or a separately reviewed
future recovery milestone.

UNKNOWN is never cleared by elapsed time, a new ref_id, restart, or another
attempt. Factual read-only reconciliation is required.

## Prototype Q62 successor

Do not weaken historical evaluate_q62_readiness.

Add a separate prospective evaluator, conceptually
evaluate_q62_tiny_live_readiness, which retains all existing fresh-proof,
identity, ownership, budget, signal-input, recovery, flat-baseline and
unresolved-effect checks.

Its capability input is the new prototype admission rather than a fabricated
READY_FOR_L42 CapabilityReport.

A ready result means only READY_FOR_L43_PROTOTYPE_READ_ONLY. It grants no trade
authority and performs no provider mutation.

Any unexpected L41R6 fact, missing manual-close policy, stale proof, account
mismatch, non-flat baseline, working/unknown order, MAY_HAVE_OCCURRED effect,
budget drift, stale signal, or recovery blocker returns BLOCKED.

## Manual-close escalation

The first tiny-live trial is explicitly armed by the single trusted user.
Arming must make the manual fallback visible in the reviewed plan: automated
exit is best effort under exact proposal review, and an unsupported/residual
close may require the user to close the <=$10 position manually.

Do not create repeated confirmation ceremony beyond the existing explicit live
arming unless implementation exposes a concrete need.

MANUAL_CLOSE_REQUIRED:

- disables every further automated entry/order;
- preserves source/config/account/ownership/effect evidence;
- permits read-only reconciliation;
- does not let the bot place a replacement sell;
- remains until a separately accepted reconciliation proves the position/order
  state resolved.

## Production maturity

This pivot is deliberately prototype-specific.

Before repeated unattended production trading in P7, revisit whether the product
needs stronger provider-qualified automatic residual handling, additional
bounded recovery authority, or a different position-sizing/execution model.
The tiny-live pivot must not be cited as proof of generic fractional execution
limits.

## Next source checkpoint

Implement the additive prototype capability adapter and prototype Q62 evaluator.
PROTECTED_EFFECTS=0.

No OAuth, browser, MCP session, tools/list, account read, order review, place,
cancel, Q62 real observation, L43, Q63, or FINAL_HOLDOUT access is authorized by
that implementation checkpoint.

Mapped CI and independent exact-source review precede any Q62 protected
readiness observation.