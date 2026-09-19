# Architecture 111 — Personal-Desktop Unattended Daily Cycle Authority

Status: frozen PD4-G0 design checkpoint; documentation only; no production effect authorization.

## 1. Scope and decision

Architecture 111 completes the authority model that Architecture 110 intentionally left unresolved before true unattended daily simulated-paper operation.

It freezes four missing production facts:

1. how an unattended wake determines which completed XNYS session may be captured;
2. how rolling strategy history becomes authoritative without relying indefinitely on the manual offline seed;
3. how a strategy decision is durably finalized before its modeled execution-session open is known; and
4. how a later independently verified C3 daily bar supplies the simulated next-open reference for settlement.

The central decision is:

> Unattended simulated-paper operation is a two-phase daily cycle. A strategy decision for session `E` is durably finalized before the regular open of `E`. After `E` is complete, an independently selected C3 daily snapshot for `E` supplies the verified daily-bar open used to settle that already-finalized decision and its verified daily-bar close becomes the current strategy observation for the following decision.

Architecture 111 does not authorize provider call #7, install or modify Task Scheduler, provision production storage, publish a real decision intent, execute Paper-v2, perform receipt recovery, submit broker orders, or enable live trading.

## 2. Controlling predecessor contracts

Architecture 111 composes and must not weaken:

- Architecture 77/82 C2/C3 one-shot provider-call, crash/recovery, child-containment, verification, terminal, and selection authority;
- Architecture 94 P1/P2 selected-C3 and deterministic strategy-plan authority;
- Architecture 102 personal-desktop security profile;
- Architectures 103–109 Paper-v2 account, supervised execution, mutation, reconciliation, and receipt-recovery authority;
- Architecture 110 unattended invocation, scheduler-as-wakeup-only, PD2A mutex, Architecture-67 idempotency, and effects-closed launcher authority;
- the exact `XNYS` descriptor `nyse-regular-sessions-1998-2100-v1` and existing modeled trading-session ordering;
- the existing `ManualPaperStrategyPlan`, checkpointed request, paper operation, and deterministic downstream identities.

No wall clock, scheduler trigger, filename, directory order, provider response, manually supplied selection ID, mutable cache, or process lifetime may replace those authorities.

## 3. Threat and integrity model

Architecture 111 is designed for the accepted closed, private, single-owner Windows desktop threat model. It protects primarily against unattended operational and implementation failures:

- a scheduler wake occurring early, late, twice, or after reboot;
- a process attempting to create a decision after the intended execution open is already knowable;
- stale market data being treated as current because the scheduler ran;
- a provider/capture failure causing a blind retry or a different session to be silently substituted;
- a rolling history gap being hidden by an offline/manual seed or filesystem discovery;
- a later daily-bar open influencing a decision that is represented as pre-open;
- duplicate or conflicting decision publication;
- duplicate Paper-v2 settlement;
- process restart between decision finalization and settlement;
- account-predecessor drift between decision creation and later execution;
- missed sessions being automatically backfilled into multiple fresh effects;
- a late scheduler launch manufacturing an invocation for an already-open session.

It does not defend against malicious Administrator/SYSTEM/physical control or a malicious process already controlling the approved `Trading` token, consistent with Architecture 102 and C3.

## 4. Daily-cycle terminology

For one modeled XNYS trading session `S`:

```text
selected daily snapshot S
    open(S)  = verified C3 daily-bar open reference for settlement of a decision targeting S
    close(S) = verified current strategy observation used when preparing the decision targeting next_session(S)
```

The terms `open(S)` and `close(S)` mean the exact `open` and `close` Decimal fields in the selected, canonical, independently verified Alpaca SIP `1Day` C3 artifact for session `S`.

They are not represented as an official NYSE opening-auction price or an official closing-auction price. Architecture 111 freezes only the project's verified Alpaca daily-bar semantics.

## 5. Source-owned XNYS regular-open timing policy

Architecture 111 introduces a pure source-owned timing policy conceptually named:

```text
XNYSRegularSessionTimingPolicyV1
```

For every modeled XNYS trading session, version 1 defines:

```text
regular_open(session) = 09:30:00 America/New_York on session.session_date
```

The value is converted through `zoneinfo` to an aware UTC instant. DST is therefore resolved by the named exchange timezone, not fixed UTC offsets.

The policy is separate from the existing `MarketCalendar` protocol. Architecture 111 does not add clock-of-day behavior to `NYSEMarketCalendar` or change its session identities/order.

The policy supplies only the regular-open deadline and the modeled `submitted_at` / `filled_at` instant used by the existing retrospective simulated-paper request.

Early closes do not change the regular-open rule. Any modeled-calendar contradiction or unsupported date fails closed.

## 6. Scheduler and wall-clock rule

Task Scheduler remains an untrusted wake-up source exactly as Architecture 110 requires.

A wake may provide no semantic trading arguments. The runtime obtains a factual current UTC timestamp only after source-owned configuration and authority prerequisites are validated.

The clock may answer questions such as:

```text
which local New York date is currently observed?
has regular_open(E) already passed?
does the existing C3 completed-session derivation reconcile with intended session S?
```

The clock may not nominate arbitrary market-data identity, selection identity, decision identity, operation identity, or retry authority.

A scheduler wake after `regular_open(E)` must never create a new decision for `E`.

## 7. Unattended completed-session capture derivation

For version 1, the unattended profile is source-owned and initially remains the accepted one-symbol SPY strategy profile.

When an unattended wake determines that session `S` is the exact completed session eligible for acquisition, the runtime derives the existing C3 request rather than accepting semantic CLI values:

```text
ordered_universe           = source-owned unattended universe
request_window_start_date  = S
request_window_end_date    = S
target_session_date        = next_session(S)
```

This intentionally satisfies the existing C3 contract:

```text
authorized_snapshot_session = S
authorized_snapshot_session < target_session_date
existing completed-session derivation(requested_at_utc) = S
```

C3 remains the only provider-effect authority. Architecture 111 does not create another Alpaca adapter, endpoint, retry loop, fallback feed, or provider transaction model.

## 8. Separate unattended market-data effect gate

Architecture 111 introduces a new source-owned gate, initially and normally false:

```text
PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = False
```

This gate authorizes only entry into the reviewed unattended composition that may reach the existing C3 one-shot capture authority.

It does not authorize:

- decision publication;
- Paper-v2 execution;
- receipt recovery;
- storage provisioning;
- Task Scheduler installation/modification;
- broker-paper or live execution.

Provider call #7 remains unauthorized until a later explicit acceptance checkpoint changes only the reviewed effect state required for exactly one acceptance invocation.

## 9. Session-indexed selected-C3 read authority

The scheduler cannot supply selection IDs. Unattended production therefore needs a source-owned read that resolves a required session to exactly one selected C3 lineage.

Architecture 111 introduces a session-indexed P2 conceptually shaped as:

```text
read_selected_snapshot_for_session(session, unattended_profile)
```

The read boundary must derive the exact canonical C3 request material for that profile/session and locate exactly one durable `SUCCESS_SELECTED` lineage matching it under the current C1 authority.

It must then reuse the existing P2 verification path to:

- validate production SQLite authority read-only;
- validate complete selected C3 lineage;
- derive the canonical artifact path from durable snapshot identity;
- safely reopen the exact final artifact;
- reconcile file identity, SHA-256, byte length, terminal and selection digests;
- independently verify canonical daily-snapshot bytes;
- bind the successful read to the current C1 authority.

Zero matches or more than one matching authority candidate is `BLOCKED`.

Filesystem discovery, newest-file selection, filename parsing as authority, directory ordering, and caller-supplied fallback selection IDs are prohibited.

## 10. C3-authoritative rolling strategy history

The existing `StrategyHistorySeed` remains a deterministic pure data container whose v1 source classification is explicitly `OFFLINE_SEED` and `authoritative=False`. Architecture 111 does not silently redefine that schema.

Instead it introduces a production outer proof conceptually named:

```text
SelectedC3StrategyHistoryBinding
```

The binding contains an ordered, bounded set of exact selected-C3 session/artifact identities and proves that the strategy history seed bytes are constructed from those independently verified snapshots.

For the existing `MovingAverageCrossoverConfig(short_window=3, long_window=5, desired_quantity=1)`, the first unattended decision requires:

```text
five consecutive selected C3 sessions strictly preceding current decision session S
+ selected C3 snapshot S
```

The history binding must prove:

- one symbol matching the unattended profile;
- exact XNYS consecutive-session order;
- every source bar comes from a current-C1 selected P2 read;
- no duplicate or missing session in the required suffix;
- no session at or after the current decision session enters the seed;
- exact canonical seed bytes/digest/length reconcile with those selected snapshots.

No filesystem scan or manually supplied offline artifact may fill a gap in production unattended history.

## 11. Warm-up state

Cold unattended deployment begins in a non-trading warm-up state until authoritative history is sufficient.

For the current long window of five, normal startup requires six consecutive selected C3 daily snapshots before the first new decision can be formed from an entirely C3-backed chain: five historical sessions plus the selected current session.

During warm-up:

```text
market-data capture may be separately authorized
decision publication remains unauthorized
Paper-v2 unattended execution remains unauthorized
```

Insufficient history reports a stable classification such as:

```text
WARMING_UP / INSUFFICIENT_AUTHORITATIVE_HISTORY
```

It is not an error that authorizes use of the old offline seed.

## 12. Two-phase strategy construction

Architecture 111 splits the current Architecture-94 planning path at the point before next-session open-reference material enters final plan identity.

Phase 1 conceptually exposes:

```text
build_manual_paper_strategy_decision(...)
    -> PreparedManualPaperStrategyDecision
```

The decision phase owns only information valid before the intended execution-session open:

- selected current C3 snapshot and its verified close;
- C3-authoritative rolling history binding;
- verified Paper-v2 predecessor/account state;
- strategy configuration;
- one existing strategy evaluation;
- derived target and planner-relevant decision evidence;
- exact intended execution session;
- source-owned policies/profile identity;
- deterministic caller-idempotency material;
- normalized planning evidence.

It contains no execution-session open price.

Phase 2 conceptually exposes:

```text
complete_manual_paper_strategy_plan(
    prepared_decision,
    verified_execution_session_open_binding,
)
    -> existing ManualPaperStrategyPlanArtifactBinding
```

The completed final plan must remain the existing Architecture-94 final format.

Compatibility is mandatory: for identical legacy semantic inputs, the new two-phase path and the existing one-phase builder must produce byte-identical final plan serialization, plan ID, request ID, checkpointed request, and downstream deterministic identities.

## 13. Durable pre-open decision intent

Architecture 111 introduces an immutable canonical artifact conceptually named:

```text
PersonalDesktopUnattendedPaperDecisionIntent
```

It must bind at least:

```text
schema / decision-policy version
paper_account_id
predecessor checkpoint identity
current decision session S
intended execution session E = next_session(S)
selected C3 identity for S
C3 strategy-history binding identity/evidence
strategy configuration/profile identity
strategy result / no-signal result
derived target and planner decision evidence
source-owned policies
planning evidence
deterministic caller idempotency key
modeled submitted_at = regular_open(E)
modeled filled_at    = regular_open(E)
```

The artifact must not contain `open(E)` or any later market-data fact.

Its deterministic identity must not depend on wall-clock publication time, filesystem path, scheduler state, Python object identity, UUID4, or ambient process state.

## 14. Pre-open decision publication authority

Architecture 111 introduces a process-local one-shot capability conceptually named:

```text
PreOpenDecisionPublicationPermit
```

A production permit may be issued only when all required source-owned authority has reconciled and:

```text
observed_now < regular_open(decision.intended_execution_session)
```

The permit must be bound to one exact decision identity and current C1/deployment provenance. It must be non-copyable, non-serializable, non-reconstructable after process death, and consumed by one finalization attempt.

The wall-clock observation is publication/admission evidence, not deterministic decision identity.

If the open deadline has passed, no permit is issued and the cycle reports a fail-closed missed-deadline classification. The runtime may still perform read-only reconciliation but may not manufacture the missing decision retrospectively.

## 15. Separate decision-publication effect gate

Architecture 111 introduces a second new source-owned gate, initially and normally false:

```text
PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = False
```

The gate authorizes only opening the fixed decision-intent output capability after a valid pre-open permit exists.

It does not authorize market-data capture, Paper-v2 execution, receipt recovery, storage provisioning, scheduler mutation, broker-paper, or live execution.

## 16. Decision-intent output authority

Decision intents live under a fixed source-owned Paper-v2 runtime namespace, conceptually:

```text
F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

The exact production path and ACL contract must be frozen before provisioning.

Publication must use hardened Windows output patterns consistent with prior Paper-v2 authority:

- fixed validated parent/root;
- exact Trading ownership and ACL expectations;
- no-follow/reparse and pinned-object checks;
- bounded canonical bytes;
- exclusive staging;
- flush/write-through durability as supported;
- no-clobber same-parent finalization;
- read-after-finalization exact verification;
- conflict is fail-closed;
- no automatic cleanup/repair of ambiguous state;
- one-shot process-local capability.

Duplicate wakeups must converge on the same deterministic decision identity and exact canonical bytes.

## 17. Verified execution-session open binding

A finalized decision targeting execution session `E` may be completed only after session `E` itself has a selected C3 snapshot under the current C1 authority.

Architecture 111 introduces a production outer proof conceptually named:

```text
C3VerifiedDailyBarOpenBinding
```

It proves:

```text
selected snapshot session == E
selected symbol == decision symbol
open_reference_price == exact selected daily-bar open
selected snapshot C1/P2 provenance is valid
finalized decision intended_execution_session == E
```

Only after this proof exists may the implementation construct the existing internal `CallerAssertedNextSessionOpenReference` needed by the established preparation/runtime contract.

The old type remains unchanged; Architecture 111 adds stronger production provenance around its construction.

## 18. Settlement and next-decision ordering

For each newly selected completed session `S`, the v1 normal ordering is:

```text
validate/reconcile C1 and selected C3 snapshot S
-> if a finalized pending decision targets S:
       bind open(S)
       complete exact existing Architecture-94 plan
       enter Architecture-110 / A67 Paper-v2 reconciliation
       when effect authority is separately open, settle at most once
       strict post-settlement Paper-v2 reread/reconciliation
-> build C3-backed history through S
-> use close(S) + reconciled post-settlement account state
   to prepare the decision targeting next_session(S)
-> require pre-open publication eligibility
-> when decision-publication authority is separately open, finalize at most once
```

A strategy decision for `next_session(S)` therefore uses the account state after any decision targeting `S` has been reconciled/settled.

## 19. No automatic multi-session catch-up in version 1

Architecture 111 v1 deliberately does not authorize automatic multi-day backfill.

If the durable state proves that one or more required sessions were skipped such that the system would need to create multiple historical decisions/effects to catch up, the unattended cycle reports a stable gap classification and stops.

Conceptual classification:

```text
SESSION_GAP
```

A later architecture may define reviewed catch-up semantics after unattended-paper soak evidence exists. Version 1 never converts an outage into a burst of retrospective fresh effects.

## 20. Required high-level classifications

The complete controller must be able to distinguish at least:

```text
NO_NEW_COMPLETED_SESSION
CAPTURE_REQUIRED
WARMING_UP
DECISION_READY
DECISION_ALREADY_FINALIZED
EXECUTION_READY
ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
MISSED_DECISION_DEADLINE
SESSION_GAP
PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
BLOCKED
```

Names may be refined during source checkpoint design, but semantics must remain closed and fail-closed.

No classification itself carries reusable execution authority.

## 21. Idempotency and crash behavior

Architecture 111 composes existing idempotency instead of creating scheduler-level retry authority.

Required behavior includes:

```text
same completed session + same C3 selection/history/account predecessor
-> same deterministic decision identity

same finalized decision + same execution-session selected C3 snapshot
-> same completed Architecture-94 plan identity
-> same Architecture-67 operation identity

completed receipt
-> ALREADY_APPLIED / no fresh settlement

terminal transition with missing receipt
-> RECEIPT_RECOVERY_REQUIRED / no fresh settlement

provider attempt ambiguous/consumed
-> existing C3 conservative state / no blind retry

conflicting decision bytes or changed predecessor
-> BLOCKED
```

Process interruption never authorizes deletion, replacement, new idempotency material, a different selection, or a different session.

## 22. Initial scheduler deployment policy

The initial reviewed desktop deployment should use one daily wake well after New York midnight and well before regular open, with a preferred operational target of approximately:

```text
04:30 America/New_York
01:30 America/Los_Angeles when offsets align normally
```

The scheduler configuration itself must be represented in the fixed Architecture-110 scheduler contract and verified at deployment time. `StartWhenAvailable` may be used for operational resilience only if a late launch still obeys the Architecture-111 deadline rules.

A late launch after `regular_open(E)` may reconcile existing durable state and may settle an already-finalized prior decision when its required completed-session evidence exists, but it may not publish a new decision targeting already-open `E`.

The scheduler time is convenience, never authority.

## 23. New gates and compatibility with existing gates

Source-only Architecture-111 implementation keeps every real effect closed.

Existing gates remain unchanged:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED = False
```

Architecture 111 adds, initially false:

```text
PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = False
```

No single gate may imply another effect category.

## 24. Source checkpoint decomposition

Recommended implementation sequence:

```text
PD4-G0  Architecture 111 + validation/deployment plan; docs only
PD4-G1  pure XNYS regular-open/session/deadline policy
PD4-G2  session-indexed selected-C3 read + C3 strategy-history binding
PD4-G3  two-phase Architecture-94 decision/final-plan construction
PD4-G4  canonical durable decision intent + pre-open publication capability
PD4-G5  zero-argument unattended C3 composition; market-data gate false
PD4-G6  complete daily-cycle controller/orchestrator; all real gates false
PD4-G7  exact source review, focused gates, one final broad certification,
        genuine Trading-principal read-only qualification
```

No source checkpoint in G1–G7 authorizes a production effect merely because implementation/tests exist.

## 25. Protected deployment sequence after source certification

After G7 acceptance, real-world deployment remains staged and individually authorized:

```text
D1  provision/verify fixed unattended decision/invocation storage namespaces
D2  install/verify the zero-semantic-argument Task Scheduler task with effects closed
D3  authorize exactly one unattended C3 acceptance capture (provider call #7)
D4  close/reconcile the capture effect state
D5  capture-only warm-up until required consecutive C3 history exists
D6  authorize exactly one pre-open decision publication with Paper-v2 execution closed
D7  close/reconcile decision-publication authority
D8  after the execution session completes and selected C3 evidence exists,
    authorize exactly one first unattended Paper-v2 settlement
D9  close all execution effects and perform strict read-only reconciliation
D10 begin a bounded unattended simulated-paper soak under separately accepted gates
```

Each effect checkpoint requires explicit operator approval immediately before the protected effect.

## 26. Non-goals

Architecture 111 does not implement or authorize:

- an intraday/opening-print provider endpoint;
- an NYSE opening-auction-price claim;
- provider retry/fallback outside C3;
- automatic multi-session catch-up;
- broker-paper or live order submission;
- permanently armed receipt recovery;
- scheduler semantic trading arguments;
- multi-host/distributed coordination;
- margin, leverage, shorts, options, or crypto;
- indefinite security-layer expansion after unattended-paper acceptance.

After Architecture-111 unattended simulated-paper acceptance, the engineering emphasis should move to operational soak/reliability and then broker-paper integration.

## 27. Acceptance criteria

Architecture 111 is accepted when design and later source validation prove:

```text
scheduler remains wake-up only
completed-session capture is source-derived and reconciles with existing C3 authority
provider call semantics remain Architecture-77/82 one-shot and conservative
rolling production strategy history is provably selected-C3-backed
legacy offline seed is never silently promoted to unattended production authority
a strategy decision is deterministic and finalizable without knowing execution-session open
no new decision can be published after its intended execution-session regular open
decision publication has an independent one-shot capability and closed-by-default gate
execution-session open comes only from an independently selected C3 daily bar
two-phase completion preserves the existing final Architecture-94 plan bytes and identities
same decision/open evidence converges on the same A67 operation
missing receipt cannot become fresh execution
missed sessions do not trigger automatic multi-day catch-up
all real effects remain separately gated
provider/broker/live authority remains unchanged until explicit later checkpoints
```
