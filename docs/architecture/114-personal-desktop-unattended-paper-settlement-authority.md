# Architecture 114 — Personal-Desktop Unattended Paper Settlement Authority

Status: frozen PD4-D8/D9 source-design checkpoint; documentation only. No Paper-v2 execution, receipt recovery, market-data capture, decision publication, storage provisioning, scheduler mutation, broker effect, or live effect is authorized by this document.

## 1. Scope and decision

Architecture 114 defines the production composition required to consume one already-finalized Architecture-111 unattended decision after its intended execution session `E` has completed and an independently selected current-C1 C3 snapshot for `E` exists.

The repository already contains the required lower-level primitives:

- finalized unattended decision discovery and exact storage verification;
- current-C1 session-indexed selected-C3 reads;
- `C3VerifiedDailyBarOpenBinding` construction;
- `complete_manual_paper_strategy_plan(...)` for the existing Architecture-94 final plan;
- PD4-C unattended Paper-v2 startup qualification under the existing PD2A mutex;
- PD4-D unattended Paper-v2 execution composition;
- Architecture-67 operation/receipt/idempotency semantics;
- strict Paper-v2 account/lineage read and receipt-recovery qualification.

Architecture 114 does not redesign those primitives. It freezes how a production D8 settlement boundary and independent D9 reconciliation boundary may compose them.

The central decision is:

> D8 is a zero-semantic-argument settlement-only production boundary. It independently re-derives the exact finalized decision targeting the current completed session, selected-C3 evidence for both the decision session and execution session, verified `open(E)`, the exact Architecture-94 final plan, current Paper-v2 account/predecessor truth, and PD4/A67 startup state. A fresh Paper-v2 effect is possible only through the existing unattended-execution authority, with only the unattended-execution gate opened process-locally for at most one exact execution composition call and restored in `finally`. D8 never performs receipt recovery. D9 is a separate fresh-process, all-gates-closed read-only reconciliation that independently proves the exact durable operation/receipt/account-lineage outcome; D8's return value is never acceptance authority.

Architecture 114 may be implemented source-only while D5 warm-up continues. It does not authorize the first real D8 effect; that remains a later protected checkpoint after D7 has been accepted and the finalized decision's execution session has completed with exact selected C3 evidence.

## 2. Controlling predecessor contracts

Architecture 114 composes and must not weaken:

- Architectures 77/82 C2/C3 transactional market-data, selection, verification, and ambiguity rules;
- Architecture 94 deterministic strategy-plan identity and Paper-v2 planning contracts;
- Architecture 102 dedicated non-admin `Trading` security profile;
- Architectures 103–109 Paper-v2 account, PD2A mutex, Architecture-67 execution, output, reconciliation, mutation, and receipt-recovery authority;
- Architecture 110 unattended invocation/storage/startup/execution semantics;
- Architecture 111 two-phase decision/settlement ordering and verified execution-session open binding;
- Architecture 112 D5 capture-only separation;
- Architecture 113 D6/D7 finalized decision-publication authority and independent reconciliation;
- the existing eight closed-by-default production effect gates.

No G6/D7 public result, scheduler metadata, caller-supplied session or decision ID, filesystem discovery, filename ordering, process exit code, cached object, or process lifetime may replace durable/source-owned authority.

## 3. D8 zero-semantic-argument boundary

D8 is a distinct production entry point and accepts no semantic trading arguments.

The caller may not supply or override:

```text
paper account ID
selected snapshot / selection ID
finalized decision ID
decision session
execution session
history seed
strategy parameters
open reference price
invocation ID
operation ID
application ID
Paper-v2 path
retry count
recovery target
effect flag
provider/broker identity
```

All semantic facts are source-owned or freshly derived from current durable authority.

D8 must not call G5, open the market-data gate, publish a new decision, provision storage, modify Task Scheduler, submit a broker order, or enter live authority.

## 4. Initial admission: all eight gates closed

D8 may begin only when all eight committed production effect gates are exact booleans and `False`:

```text
market-data capture        = False
decision publication       = False
Paper-v2 production        = False
Paper-v2 recovery          = False
supervised execution       = False
receipt recovery           = False
unattended execution       = False
storage provisioning       = False
```

Any open or non-boolean gate is `BLOCKED` before settlement qualification.

Every committed gate constant remains `False` in source.

## 5. Independent settlement re-derivation

D8 must not consume D7-A, D7-C, D7-D, or G6 public output as authority.

It independently derives and validates at least:

```text
current production C1 authority
genuine non-admin Trading token
current completed XNYS session E
current-C1 selected C3 snapshot for E
exact finalized unattended decision targeting E
current-C1 provenance for finalized-decision discovery/storage
original selected C3 snapshot S bound into that decision
exact decision current/history C3 evidence
verified daily-bar open binding from selected C3(E)
exact existing Architecture-94 final plan
current Paper-v2 account identity and predecessor
exact unattended invocation identity/storage state
exact Architecture-67 operation identity/state
current receipt-recovery qualification
```

A contradiction, missing required durable artifact, multiple authority candidates, provenance mismatch, account/predecessor mismatch, malformed durable state, or security/identity ambiguity fails closed.

D8 never substitutes an offline history seed or caller-provided open price.

## 6. Finalized decision and execution-session rule

Fresh settlement is possible only for an already-finalized exact decision whose:

```text
intended_execution_session == current completed session E
```

The finalized decision must be independently replayed from canonical bytes and exact current-C1 storage/discovery provenance.

D8 must independently reread the selected C3 snapshot for the decision's original selected session `S` and require exact equality with the decision's persisted `current_c3` evidence.

D8 must independently read selected C3 for `E` and require that it is exact current-C1 evidence for `E`.

No decision targeting a future, prior, ambiguous, or caller-selected session may settle.

If there is no finalized decision targeting the current completed session, D8 performs no Paper-v2 effect.

## 7. Verified `open(E)` and exact final-plan reconstruction

The execution reference comes only from the exact selected C3 daily snapshot for `E` through the existing reviewed verified-open binding.

Required composition:

```text
finalized prepared decision for S -> E
+ current-C1 selected C3(E)
-> C3VerifiedDailyBarOpenBinding
-> complete_manual_paper_strategy_plan(...)
-> existing Architecture-94 ManualPaperStrategyPlanArtifactBinding
```

The completed plan must preserve the existing deterministic Architecture-94 contract. D8 must verify at least:

- exact paper-account identity;
- exact predecessor checkpoint bound into the finalized decision;
- exact selected-C3 assertion and strategy decision evidence;
- exact caller-idempotency key;
- exact execution session `E`;
- exact verified open binding from selected C3(E);
- canonical plan bytes/digest/length/IDs;
- no caller-supplied or wall-clock price substitution.

Architecture 114 introduces no new plan schema or operation identity.

## 8. PD2A mutex and existing startup/execution authority

D8 must reuse the existing PD4-C/PD4-D startup/execution composition and the existing PD2A account mutex. It must not add a second account mutex or hold a new outer PD2A lock across a nested call that already acquires the nonreentrant account mutex.

The existing startup composition remains responsible for predecessor-sensitive reconciliation under the mutex, including:

```text
strict account read/revalidation
exact invocation identity/storage inspection
Architecture-67 operation inspection
already-applied convergence
terminal missing-receipt detection
final account/operation reconciliation
```

D8 supplies only independently reconstructed source-owned inputs to that reviewed boundary.

If startup classification is already applied, D8 performs zero write and zero fresh execution.

If startup classification requires receipt recovery, D8 reports that state and stops. It does not open receipt-recovery authority.

## 9. Unattended execution gate isolation

A fresh Paper-v2 settlement effect may be attempted only after complete D8 admission succeeds and the existing startup/execution path proves it is eligible.

During the exact existing unattended execution composition call, the process-local gate state must be:

```text
unattended execution       = True
market-data capture        = False
decision publication       = False
Paper-v2 production        = False
Paper-v2 recovery          = False
supervised execution       = False
receipt recovery           = False
storage provisioning       = False
```

D8 may change only the unattended-execution gate and must restore it to `False` in `finally`.

D8 has an execution-attempt budget of one. It may call the reviewed unattended Paper-v2 execution composition at most once per invocation.

No process exit code, scheduler history, exception, timeout, ambiguous result, or partial output grants same-invocation or automatic later retry authority.

## 10. No receipt recovery in D8

Architecture 114 deliberately separates fresh unattended execution from receipt recovery.

If durable inspection proves an exact terminal operation with missing receipt:

```text
RECEIPT_RECOVERY_REQUIRED
```

D8 stops with all gates closed.

It must not:

- open the receipt-recovery gate;
- synthesize or reconstruct a receipt through fresh execution;
- create a new invocation/operation to make progress;
- delete/repair operation state;
- treat scheduler retry as recovery authority.

Any later unattended receipt-recovery policy requires a separate architecture/effect checkpoint informed by soak evidence.

## 11. Durable-state-first acceptance

D8's execution return value is diagnostic only. It is not final acceptance authority.

D8 should perform conservative immediate reconciliation where existing reviewed composition already provides it, but the first real settlement is accepted only after D9 runs independently in a fresh process with all gates closed.

A D8 result may distinguish at least:

```text
SETTLEMENT_NOT_READY
SETTLEMENT_COMPLETED
SETTLEMENT_ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
SETTLEMENT_OUTCOME_AMBIGUOUS
BLOCKED
```

Exact naming may reuse established repository classifications where clearer, but only durable D9 evidence closes the protected D8/D9 milestone.

`real_effect_performed` is diagnostic only and must accurately indicate whether the exact unattended Paper-v2 effect boundary was crossed.

## 12. D9 independent post-settlement reconciliation

D9 is a separate zero-semantic-argument, all-gates-closed, read-only production boundary.

It runs in a fresh non-admin `Trading` process and does not consume D8 public output as authority.

D9 independently re-derives:

```text
current C1 / Trading token
current completed execution session E
selected C3(E)
exact finalized decision targeting E
original selected C3(S)
verified open(E)
exact Architecture-94 final plan
expected unattended invocation identity
expected Architecture-67 operation/application identity
Paper-v2 account/lineage
operation/receipt durable state
```

D9 success requires durable evidence equivalent to:

```text
finalized decision remains exact
selected C3 provenance remains exact
verified open(E) / final plan remain exact
expected invocation is finalized-identical
expected Architecture-67 operation is ALREADY_APPLIED
exact completed receipt exists and verifies
successor checkpoint is exact
Paper-v2 current account tip == exact successor checkpoint
account lineage contains the exact expected transition
current C1 / Trading token remain valid
all eight gates remain false
```

If the durable operation is terminal with a missing receipt, D9 reports `RECEIPT_RECOVERY_REQUIRED`; it does not recover it.

Conflicting, malformed, unknown, staging, multiple-candidate, account-lineage, C1, security, or provenance ambiguity is `BLOCKED`.

## 13. Account predecessor and successor rules

The finalized decision binds predecessor checkpoint `P`.

Before a fresh settlement effect, current Paper-v2 account truth must still be compatible with `P` under the existing startup/Architecture-67 contract.

Successful fresh settlement must converge on one exact deterministic successor `Q` derived by the existing plan/operation machinery.

D9 success requires:

```text
finalized decision predecessor == P
expected operation predecessor == P
completed receipt / application == exact expected identities
current Paper-v2 account tip == Q
lineage proves P -> Q through the exact expected operation
```

An unrelated account advance, stale predecessor, alternate operation, or multiple candidate successor fails closed.

## 14. Crash, ambiguity, duplicate, and later-wake semantics

Architecture 114 inherits Architecture-67/110 durable-state-first behavior.

After crash or ambiguous D8 termination, a later wake starts from fresh authority. It does not use the previous process's exit code or in-memory state.

A later wake may:

- converge read-only on exact `ALREADY_APPLIED`;
- report exact `RECEIPT_RECOVERY_REQUIRED`;
- consider one fresh effect only if the existing startup authority independently classifies the exact same deterministic invocation/operation as safely executable and all D8 admission rules still hold.

It may not:

- invent a new caller idempotency key;
- create a different operation for the same decision;
- delete staging/conflicting state;
- retry an ambiguous provider effect;
- perform multi-session catch-up;
- skip over a missing receipt.

## 15. Scheduler separation

Architecture 114 does not change the installed D5 capture-only scheduled task.

Source work and the first protected D8/D9 acceptance remain separate from scheduler mutation.

After D8/D9 acceptance, D10 soak architecture may decide how to compose capture, publication, and settlement wake behavior operationally. That later checkpoint must preserve zero-semantic-argument wakeups and all effect isolation rules.

## 16. Prohibited effects

D8/D9 source work must not:

- call G5 or perform provider capture;
- publish a new decision;
- provision/repair storage;
- perform receipt recovery;
- mutate Task Scheduler;
- modify the armed D5 worktree/task;
- submit broker-paper orders;
- enter live trading;
- perform historical backfill/catch-up.

D9 additionally must perform no Paper-v2 mutation of any kind.

## 17. Required source tests

Source acceptance must prove at least:

### Re-derivation and provenance

- zero semantic arguments;
- genuine current C1 and Trading token required;
- no G6/D7 result consumed as authority;
- exact finalized decision for current completed session required;
- exact original selected C3 and current execution-session C3 required;
- exact current-C1 discovery/storage provenance required;
- verified `open(E)` comes only from selected C3(E);
- exact Architecture-94 final plan reconstruction and replay;
- exact predecessor/account binding.

### Effect containment

- all eight gates initially closed;
- only unattended-execution gate may become true;
- all seven companion gates remain false;
- execution gate closes on success/no-op/exception;
- at most one existing unattended execution composition call per D8 invocation;
- no receipt-recovery/provider/publication/provisioning/scheduler/broker/live boundary is reachable.

### Durable convergence

- already-applied state performs zero fresh effect;
- missing receipt reports recovery required without recovery;
- conflicting/staging/malformed/unknown invocation or A67 state blocks;
- account predecessor drift blocks clean execution admission;
- D8 return alone cannot satisfy D9;
- D9 independently reconstructs exact decision/open/plan/invocation/operation;
- D9 requires verified receipt, exact successor checkpoint, exact account tip, exact lineage, and A67 already-applied state;
- duplicate/repeated D9 is read-only and deterministic;
- public results expose no reusable authority/capability/handle/path/credential/raw C1.

No source test may require a real provider, Paper-v2 mutation, scheduler mutation, broker effect, or live effect.

## 18. Protected D8/D9 first-settlement sequence

Source acceptance does not authorize the real D8/D9 effect sequence.

After one D7 decision has been independently accepted and its intended execution session `E` has completed with exact selected C3(E), the protected sequence is:

```text
D8-A  fresh Trading read-only settlement qualification
      -> exact source/runtime/C1/account
      -> exact finalized decision targeting E
      -> selected C3(S) + selected C3(E)
      -> verified open(E)
      -> exact final Architecture-94 plan
      -> exact PD4/A67 startup classification
      -> all eight gates closed

D8-B  explicit approval for one zero-semantic-argument settlement invocation
      -> at most one unattended Paper-v2 execution composition call
      -> only unattended-execution gate temporarily open
      -> no receipt recovery

D9-A  fresh Trading all-gates-closed independent reconciliation
      -> exact finalized decision / C3 / open / plan
      -> exact invocation / operation / receipt
      -> exact successor checkpoint and Paper-v2 lineage/account tip
      -> A67 already-applied

D9-B  acceptance record / source-host certification closeout
```

If D8-A reports `ALREADY_APPLIED`, skip fresh execution and proceed directly to D9-A.

If D8-A or D9-A reports `RECEIPT_RECOVERY_REQUIRED`, stop. Recovery remains separately protected.

## 19. Acceptance criteria

Architecture 114 is accepted when source and later protected evidence prove:

```text
D8 is zero-semantic-argument and settlement-only
D8 independently re-derives exact finalized decision and selected-C3 state
verified open(E) comes only from exact current-C1 selected C3(E)
existing Architecture-94 final plan is reconstructed exactly
existing PD4-C/PD4-D/A67 authority is reused rather than bypassed
only unattended-execution gate may open process-locally
one D8 invocation has at most one fresh execution composition call
receipt recovery remains closed and separate
D8 return value is non-authorizing
D9 independently proves exact durable operation/receipt/successor/account lineage
already-applied converges with zero fresh effect
ambiguous/conflicting/missing-receipt state fails closed
armed D5 scheduler remains unchanged
provider/publication/provisioning/scheduler/broker/live effects remain prohibited
real first settlement remains separately and explicitly authorized
```

## 20. Next milestone after D8/D9

After the first D8/D9 settlement is accepted, the next protected operational checkpoint is D10: a bounded unattended simulated-paper soak. D10 must freeze a concrete soak duration/cycle target and operator stop/escalation criteria before the installed scheduler is expanded beyond its current capture-only role.

Broker-paper integration remains a later PD5 milestone and is not authorized by Architecture 114.
