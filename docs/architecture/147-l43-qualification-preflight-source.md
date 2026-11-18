# Architecture 147 — L43-Q1 qualification preflight source

## Status

FROZEN DESIGN for the next source-only checkpoint:
`ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE`.

Baseline executable source is the accepted/integrated RHC4-C2 identity:
`4f560a74b04ecba85c7b312364a9e4e7b30e57b6` / tree
`b422ef66d88b184bdbe12788546e6b2ffd083846`.

This document authorizes source design/implementation and fake verification only.
It does not authorize a real Robinhood/Alpaca preflight, OAuth/browser activity,
review, placement, cancellation, retry, durable effect mutation, Q63, or
`FINAL_HOLDOUT` access.

## Objective

Add one source-owned L43 qualification harness that can later perform a separately
reviewed **read-only** protected preflight against the accepted RHC4 production
composition. The preflight must freshly re-derive the facts needed to decide
whether an exact L43 entry plan is eligible for a later authorization review,
while making it impossible for the preflight itself to review or place an order.

Q1 closes the gap between accepted source composition and the first real-money
effect boundary. It does not cross that effect boundary.

## Fixed predecessor contracts

Q1 reuses rather than replaces:

- Q62 consumed pristine origin and its accepted read-only readiness evidence;
- RHC2/RHC3 complete account-wide SPY order-scope proof and retained evidence;
- RHC3P exact provider-order binding and repeatable factual settlement;
- RHC4-C2 production composition, public Robinhood session seam and serialized
  Stop/effect boundary;
- `L43ProductionPreEffectComposition`,
  `observe_l43_pre_effect`, `L43ProductionOwner`, and existing current
  Robinhood/Alpaca read paths;
- the production default-deny exact-plan authorizer.

Q1 must not mutate the consumed Q62 journal or replace retained RHC2/RHC3
evidence. It must not weaken the RHC3P no-retry/UNKNOWN contract.

## Registered checkpoint shape

Implementation must add one registered checkpoint owned by Architecture 147.

Required operational shape:

- source implementation/certification: fake-only;
- registered protected **preflight**: read-only provider/credential activity only;
- registered `execute`: **None** in Q1;
- no review/place/cancel tool can be reached from the Q1 preflight;
- no stage authorization object can be minted by Q1 preflight;
- no GUI Start, CLI boolean, environment flag, Q62 PASS, RHC2/RHC3 proof, or
  caller-built object may satisfy a future exact-plan authorization.

The later real Q1 preflight therefore remains independently protected even after
source acceptance/integration.

## Preflight input authority

The real preflight accepts no caller-supplied account number, provider order ID,
source identity, capability status, plan digest, decision, quantity, or authority.

It derives or binds:

1. exact current executable HEAD/tree and accepted source ancestry;
2. canonical RHC4 configuration and strategy binding;
3. canonical Q62 origin and current L43 durable-state identity;
4. retained RHC3 account-wide order-scope authority;
5. canonical agentic account from provider reads;
6. current SPY position and exhaustive relevant SPY orders;
7. current L43 durable state as read-only qualification input;
8. current session authority;
9. current accepted Alpaca signal inputs and decision;
10. the exact detached L43 pre-effect result.

A stale/mismatched source, missing retained evidence, unavailable state, pending
or ambiguous effect, non-flat/manual holdings, unsupported session, stale signal,
provider-read failure, pagination ambiguity, or unexpected account/order state
blocks qualification.

Q1 must not settle or append durable state. If a bound WORKING/PARTIAL order
requires accepted RHC3P settlement, the read-only preflight returns a typed
settlement-required/blocking result. Settlement remains a distinct factual
runtime path.

## Preflight outcomes

The source-owned result is closed and sanitized. At minimum it distinguishes:

- `READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW`
- `NO_ACTION_SIGNAL`
- `PENDING_SETTLEMENT_REQUIRED`
- `MANUAL_CLOSE_REQUIRED`
- `BLOCKED`

READY is possible only for the genuine current BUY entry path while flat, with
requested entry risk positive and no greater than the accepted $10 bound, no
consumed entry, no unresolved effect, and all current read/session/signal/source
facts accepted.

READY is not order authority.

## Exact challenge material

A READY result produces an immutable qualification challenge digest binding at
least:

- source HEAD/tree;
- configuration digest;
- binding digest;
- account fingerprint;
- target session;
- current durable state sequence and tail digest;
- fresh pre-effect facts digest;
- detached plan binding digest;
- requested entry dollars;
- exact stage `ENTRY_PLACEMENT`;
- checkpoint/schema version.

The preflight exposes no raw account number, credentials, bearer token, provider
payload, browser state, or reusable capability.

The challenge is evidence for a later source/effect milestone. Q1 does not
construct `L43StageAuthorization`.

## Provider-call budget for the later real preflight

The later protected read-only Q1 invocation may use only the already accepted
read paths necessary to re-derive current facts. It may perform credential/OAuth
work required by those reads and may perform the accepted Alpaca current-signal
read.

Maximum mutation/effect counts remain:

- Robinhood review: 0
- Robinhood placement: 0
- Robinhood cancellation: 0
- broker mutation: 0
- L43 durable-state append/reservation: 0
- Q62 journal mutation: 0
- FINAL_HOLDOUT access: 0

All provider reads must retain existing bounded pagination and sanitized evidence
rules.

## Session and retry policy

Q1 reuses the provider-owned lazy session seam accepted by RHC4; it does not add
a second MCP client.

External implementation survey refreshed on 2026-11-17:

- `EUGMsub/RobinhoodAgenticTrader`, commit
  `fe620377b4e8fbd7b236ba07c45390c120e69f32`,
  `src/mcp_client.py` and `src/oauth.py`: lazy MCP initialization,
  `Mcp-Session-Id`, initialized notification, structured content, PKCE,
  string-valued `dollar_amount`, caller `ref_id`, and bounded session/401
  recovery.
- `kevin1chun/robinhood-for-agents`, commit
  `16b3d800e7f29e9d450f45663d054a7b5adcd4b3`,
  `src/server/official/forward.ts`, `docs/MODES.md`, and
  `docs/official-mcp-tools.json`: provider-owned cached Streamable HTTP client,
  fresh bearer injection, official Trading MCP forwarding, structured content,
  current equity-order schema, and refusal to automatically retry a potentially
  landed write unless the tool is explicitly read-only/idempotent.

These repositories are corroborating implementation evidence, not authority.
Where public examples differ, the Trading Bot retains its stricter rule:
`ref_id` is correlation/idempotency evidence and does **not** create automatic
retry authority after an ambiguous write. `MAY_HAVE_OCCURRED` and factual
reconciliation remain authoritative.

## Human/effect boundary

Q1 deliberately stops before human order authorization.

The next effect milestone may reuse the accepted Architecture-131 pattern:
prepare exact current facts, display an exact digest challenge, require one
terminal interactive TTY authorization frame bound to that challenge, revalidate
the exact facts, then cross one separately reviewed effect boundary. That future
design must not accept piped/noninteractive text, ambient environment authority,
GUI Start, or reconstructed/caller-forged stage grants.

Q1 source acceptance or a Q1 READY preflight never authorizes the future effect.

## Source verification contract

Implementation must prove with fakes that:

- import/help/construction are effect-free;
- preflight has no review/place/cancel import/call path;
- no stage authorization can escape or be fabricated;
- canonical account selection is internal;
- all read results are bounded and sanitized;
- pending/unknown/manual-close states block;
- a genuine BUY can produce READY challenge material without mutation;
- HOLD/SELL while flat produces no entry authorization path;
- source/config/account/session/signal/state drift blocks;
- provider/read failure creates no retry or effect authority;
- repeated fake preflight calls do not mutate durable state;
- current public/private seam ownership from RHC4 is preserved.

Mapped certification remains owned by the existing Architecture-147 route. No
local duplicate FULL is required when the exact mapped CI run supplies it.

## Next boundary after Q1 source acceptance

After exact-source review, certification and fast-forward integration, run exactly
one separately reviewed protected **read-only** Q1 preflight from the accepted
source using the repository-owned runner. Preserve its evidence whether READY,
NO_ACTION or BLOCKED. Do not invoke an order effect in the same checkpoint.
