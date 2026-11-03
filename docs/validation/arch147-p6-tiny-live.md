# Architecture 147 P6 — Validation contract

The P6 source checkpoint uses synthetic provider-shaped payloads only. It must
prove the following before publication:

1. P5B evidence is exactly one PASS report discovered under the stable P5B
   checkpoint evidence root, bound to source
   `7ff86d06a99bcdf349d5e20846d139a554d8be46` and tree
   `095c51cedc1c656616123c3acf88148b16b71aa2`, with zero mutation/review/
   placement/cancel effects and unchanged production state. Zero or multiple
   matching reports block, and its account fingerprint is loaded rather than
   hard-coded.
2. The P5B transport remains mutation-free and the P6 transport owns the only
   current Architecture 147 live mutation methods.
3. Tool discovery fails closed when any required tool or dollar-order schema is
   absent; no share-quantity fallback or generic dispatch exists.
4. Strategy evaluation uses only the accepted SPY 35/50 BASE_MA signal over at
   least 60 completed raw regular daily bars and never uses FINAL_HOLDOUT or
   Alpaca data.
5. Risk rejects non-SPY, short, leveraged, unsupported, over-$10 or over-$10
   gross exposure intents and proves cash/equity coverage before a BUY.
6. Plans are immutable, source- and digest-bound, sanitized, and preserve
   `PAPER_EVALUATION` as a separate non-live-eligible contract.
7. Preflight performs no place or cancel; both P6 preflight and protected
   execution require the remote feature and remote `develop` heads to equal
   local HEAD plus prospective-develop/current source authority before attempt
   creation. Execution is disarmed without both exact environment interlocks;
   create-only markers prevent retry after a possibly consumed placement;
   only terminal broker states reconcile, while partial/pending/open states
   remain stopped with the attempt consumed; post-trade reconciliation is
   finite.
8. GUI state contains no raw account number and has no arm/place/cancel button.
9. P6 state is absent after imports, tests, source admission and CI.

Focused verification covers the new policy, strategy, plan, execution,
transport, GUI and checkpoint-authority tests. Ruff check/format and the
repository source-authority evaluator are also required. GitHub owns the
registered canonical FULL certification; no local provider preflight or
execute run is part of the source checkpoint.

## Consumed-attempt correction

Synthetic tests distinguish failure before marker ownership (zero placement),
marker/initial-lifecycle failure after consumption (zero placement, no retry),
placement invocation raising (one attempted placement), and successful placement
followed by parsing, observation, reconciliation or lifecycle persistence failure
(one placement, consumed and MAY_HAVE_OCCURRED). Diagnostic persistence may also
fail without erasing the returned evidence. Each consumed scenario verifies a
second invocation makes zero additional placement calls and preserves the marker.
Open/pending/partially-filled states remain stopped and unreconciled; filled,
rejected and canceled terminal states retain truthful persisted reconciliation.
Dispatch tests use fakes to prove P6 source admission precedes delegation and
non-P6 checkpoints preserve predecessor delegation. No implementation-body,
AST-hash, line, helper-layout or ordinal pin is added by this correction.

## Historical shared cancel-result correction (before operator reachability)

The consumer audit covers every `ExecutionResult` constructor in `execute_plan`,
`_reconcile_placement`, `kill_owned_order` and `_blocked`, plus the sanitized
`execute` projection. Cancellation now distinguishes new call counts from
preserved consumed authority. Synthetic exact-owned cancellation success and
post-invocation transport failure both retain one cancel call, zero place calls,
consumption and `MAY_HAVE_OCCURRED`; neither claims terminal cancellation.
Existing or racing cancel markers block another call with zero new counts.
Unlatched kill and ambiguous ownership remain pre-cancel/no-effect. Partial
marker failures preserve consumed state without a call. Returned evidence
contains no raw provider exception text. Existing placement tests retain the
consumed-before-placement and persisted terminal-reconciliation contract.

At the time of this historical shared-result correction, the source-wide caller
search found no operator caller of `kill_owned_order`:
`P6_KILL_OPERATOR_REACHABILITY=NOT_IMPLEMENTED`. This preserved chronology
describes that earlier source state only. The later accepted/integrated P6
implementation adds the protected/disarmed operator reachability; no real kill
invocation or GUI cancellation has occurred.

## Preserved publication chronology

The accepted P6 baseline is `5330957b0c7c55d133503a1953ab38f97db31d92`, tree
`8690f9af86000447b08d6c140567796f3403e779`. Feature run `41515801379` and
develop run `41517145924` reached terminal success. Earlier feature failures
`41422233785` (`67ef2f6`), `41436540116` (`8dbee51`) and `41514454782`
(`f2b9f9a`) remain preserved; no failed attempt is rewritten or rerun. The wrapper
correction isolates current P6 admission from the frozen historical
`execute_checkpoint` body; the later test-module rename resolves collection
identity. At that historical point, this source-only correction was based on that
accepted integrated baseline and still had to earn its own admission and terminal
mapped canonical FULL. Its publication did not authorize provider, credential,
broker or live effects.

The placement-evidence correction `c665b8d2ae0bc3df39c8a249388d60605d6fa87c`,
tree `75ab3718dd92c497ab38e162db2d01980619033b`, completed GitHub run
`41530516256` successfully on attempt 1. ChatGPT exact-source review rejected
integration because the shared result abstraction misclassified cancel effects.
This was a source-level review blocker, not a CI failure. That published commit
and terminal-green evidence remain immutable. At that historical point, the
shared cancel-result correction was its ordinary child and required fresh
admission and mapped FULL; develop remained at the accepted baseline pending
independent exact-source review.


## Current exact-owned kill implementation — accepted/integrated

The accepted/integrated implementation is `f1558b97e60bb32fae2a9f1de23226d261418d99`,
tree `ed4a5a962aa6edd98235bf90dffb10e84a935b40`. Feature canonical FULL
`41575733423` passed on attempt 1; develop integration CI `41588005188` passed
on attempt 1 and reused the exact feature certification. Source review accepted
the exact durable binding, separate kill interlock, at-most-one-cancel
semantics, observation-only recovery and terminal reconciliation behavior.
All verification uses synthetic state and fakes. No real CLI, P6 preflight,
execute, credential/OAuth access, provider read, review/place/cancel, production
P6 state or FINAL_HOLDOUT access is part of this milestone.

The registered existing execution and P6 authority test modules cover:

- integrated source admission before any provider construction, including dirty,
  origin/feature/develop/branch/authority drift and unstable source;
- immutable READY plan/digest/source and exact binding validation; missing,
  mismatched or malformed bindings fail closed; no arbitrary provider ID input;
- create-only binding persistence before the first post-placement observation;
  existing/conflicting/partial bindings are preserved and persistence failures
  keep exactly one place call, consumed uncertainty and no retry;
- a separate kill arm with no placement-arm dependency;
- canonical account fingerprint and exact-order corroboration; similar SPY
  orders cannot replace the bound ID;
- zero-cancel terminal fill/cancel/rejection, one cancel for a working order,
  acknowledgement followed by exactly one immediate bounded observation;
- partial-fill cancellation of the remainder only with monotonic cumulative
  fills and exactly consistent surviving SPY position; no liquidation;
- still-working/missing/parse/account failures and cancel exceptions preserve
  uncertainty, consumption and no retry; existing cancel markers allow terminal
  observation with zero new cancel calls;
- create-only external sanitized evidence and persistence-failure truthfulness;
  raw synthetic exception/secret/account/order text is absent from kill reports;
- a kill-only fake with no review/place/sell/options/crypto/generic capabilities,
  semantic source capability checks, and the unchanged presentation-only GUI.

The shared-consumer audit includes `execute_plan`, `_reconcile_placement`,
`kill_owned_order`, `execute`, ownership helpers, operator preparation and
reconciliation, existing placement/cancel evidence tests and the P6 source
checker. `ExecutionResult`, its disposition logic and placement receipt shape
remain unchanged. Placement adds only strict ID parsing, the durable binding
inside its consumed boundary and an existing-binding pre-place stop. The
primitive no longer accepts a raw caller-supplied provider ID; it reloads the
binding. `KillResult` owns terminal cancellation reconciliation separately.
The explicit transport constructor is public for both admitted callers.

The P6 source inventory includes ownership and operator modules. Tests remain
in the existing registered P6 modules, so shared checkpoint runner, `ops.ps1`,
registry, workflow topology and historical pins need no change. Checks are
semantic; no current function-body/AST hash, line/helper-order or ordinal pin
is added. The accepted feature and develop evidence above remains GitHub-owned;
no protected effect occurred during implementation, certification or integration.
