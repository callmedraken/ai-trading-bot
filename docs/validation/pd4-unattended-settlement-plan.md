# PD4 Unattended Paper Settlement Validation Plan

Status: frozen validation plan for Architecture 114. Source work only until an explicitly approved protected D8/D9 checkpoint. This plan does not authorize Paper-v2 execution, receipt recovery, market-data capture, decision publication, storage provisioning, scheduler mutation, broker effect, or live effect.

## 1. Objective

Validate the Architecture-114 settlement composition around the repository's existing finalized-decision, verified-open, Architecture-94 plan-completion, PD4-C startup, PD4-D unattended execution, Architecture-67 operation/receipt, and Paper-v2 lineage primitives.

The source-development goal is to prepare three things before any real settlement is authorized:

1. a zero-semantic-argument D8-A read-only settlement qualification boundary;
2. a zero-semantic-argument D8-B settlement-only production boundary that may later open only the unattended-execution gate for one exact existing execution composition call;
3. a separate zero-semantic-argument D9-A all-gates-closed independent reconciliation boundary.

D5 capture-only warm-up continues naturally and remains untouched while this source work occurs.

## 2. Fixed branch/worktree separation

This source line begins from the post-D7 certification docs tip:

```text
base commit: 489b96a97d36fd28822142db9a69f0f0dd2d3d72
branch: feature/pd4-unattended-settlement
planned worktree: F:\AI\worktrees\ai-trading-bot-unattended-settlement
```

The certified D7 source identity remains historical and unchanged:

```text
certified D7 source HEAD: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
certified D7 source TREE: bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
full suite: 6302 passed, 17 skipped
```

During D8/D9 source work:

```text
armed D5 branch/worktree/task = unchanged
all committed effect gates     = False
real D8 settlement              = not authorized
receipt recovery                = not authorized
```

## 3. Validation philosophy

Each intermediate source checkpoint uses:

```text
exact changed-file review
focused pytest for affected contracts
focused Ruff check
focused Ruff format --check
git diff --check
git diff --cached --check
clean worktree/index at checkpoint boundary
```

Do not run the complete repository suite after every Codex/source modification.

Run one broad repository certification only when ChatGPT declares the D8/D9 source tree feature-complete and final for this milestone, unless a later meaningful source correction requires a replacement final certification.

Docs-only closeout after final certification does not require another full suite.

## 4. D8-A — read-only settlement qualification

### Goal

Prepare a genuine production, zero-semantic-argument, all-gates-closed Trading-principal qualification boundary that proves whether one exact finalized decision can safely enter the existing unattended Paper-v2 startup/execution path.

### Required re-derivation

D8-A must independently derive and validate:

```text
current C1 authority
genuine Trading token
current completed session E
selected C3(E)
exact finalized decision targeting E
current-C1 finalized-decision discovery/storage provenance
selected C3(S) for the decision's original selected session
exact decision C3 bindings
verified open(E)
exact Architecture-94 final plan
current Paper-v2 account/predecessor
exact PD4-C startup classification
all eight gates closed
```

D8-A must not consume G6, D7-A, D7-C, or D7-D public results as authority.

### D8-A classifications

At minimum distinguish safely:

```text
NO_SETTLEMENT_PENDING
EXECUTION_READY
ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

More-specific existing read-only classifications may be preserved where useful.

`real_effect_performed` must always be `False`.

### D8-A tests

Cover at least:

- zero semantic arguments;
- each of eight gates open/non-boolean blocks;
- genuine Trading token/current C1 required;
- no finalized decision for E -> no-settlement/no-effect;
- wrong/ambiguous/multiple finalized decision blocks;
- exact original selected C3 decision evidence required;
- exact selected C3(E) required;
- verified open binding derives only from C3(E);
- exact final plan reconstruction/replay;
- predecessor/account mismatch blocks;
- PD4-C startup classifications map exactly;
- `ALREADY_APPLIED` is read-only convergence;
- missing receipt maps to recovery required without recovery;
- public result contains no reusable authority/capability/handle/path/credential/raw C1.

No production effect may be reachable from D8-A tests.

### Model routing

Security/read-authority/cross-contract composition: **Sol High**.

## 5. D8-B — zero-argument settlement-only production source

### Goal

Prepare the source boundary that may later perform exactly one unattended Paper-v2 settlement attempt after an independently eligible durable state exists.

D8-B source remains effects-closed by default and is not production-invoked during source development.

### Required behavior

The production boundary must:

1. require all eight gates exact false at entry;
2. independently repeat current source-owned settlement re-derivation rather than trusting D8-A output;
3. fail closed on no pending finalized decision, contradiction, already-applied state, recovery-required state, or ambiguous durable state;
4. construct the exact verified open and Architecture-94 plan;
5. call only the existing reviewed unattended Paper-v2 execution composition for fresh settlement;
6. temporarily open only `PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED`;
7. restore that gate in `finally`;
8. permit at most one existing unattended execution-composition call per invocation;
9. never open receipt recovery or any companion effect gate;
10. perform conservative post-call all-gates-closed rereads but treat D9 as independent acceptance authority.

### D8-B classifications

A bounded public contract should distinguish at least:

```text
SETTLEMENT_NOT_READY
SETTLEMENT_COMPLETED
SETTLEMENT_ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
SETTLEMENT_OUTCOME_AMBIGUOUS
BLOCKED
```

Exact names may reuse established repository conventions.

### Effect-containment tests

At minimum prove:

- only unattended-execution gate can become true;
- all seven companion gates remain false;
- execution gate closes after success/no-op/exception;
- committed gate constant remains false;
- at most one existing unattended execution call occurs;
- already-applied performs zero fresh execution;
- recovery-required performs zero fresh execution/recovery;
- execution exception/ambiguous outcome never triggers same-invocation retry;
- provider/G5, decision publication, storage provisioning, scheduler, receipt recovery, broker, and live boundaries are fatal if reached.

### Model routing

Native Windows/security/order/crash/effect containment: **Sol High**.

## 6. D9-A — independent read-only post-settlement reconciliation

### Goal

Prepare a fresh-process, zero-semantic-argument, all-eight-gates-closed proof that a settlement is durably and exactly complete.

D9-A must not consume D8-A or D8-B public output as authority.

### Required re-derivation

D9-A independently reconstructs:

```text
current C1 / Trading token
current completed session E
selected C3(E)
finalized decision targeting E
original selected C3(S)
verified open(E)
exact Architecture-94 final plan
expected unattended invocation identity
expected Architecture-67 operation/application identities
Paper-v2 account and full relevant lineage
operation/receipt durable state
```

### Successful reconciliation

Only one positive classification, conceptually `RECONCILED`, is success.

It requires:

```text
finalized decision exact
selected-C3 provenance exact
verified open(E) exact
final plan exact
invocation finalized-identical
expected A67 operation ALREADY_APPLIED
exact completed receipt verified
exact deterministic successor checkpoint
current Paper-v2 account tip == successor
exact P -> Q lineage through expected operation
current C1/Trading token valid
all eight gates false throughout
```

### Failure/conservative classifications

At minimum distinguish:

```text
RECONCILED
NOT_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

`NOT_APPLIED` is diagnostic only and grants no fresh execution authority.

### D9-A tests

Cover:

- zero semantic arguments;
- all eight gates closed at entry/final;
- Trading/C1/account/token drift;
- exact decision/C3/open/plan replay;
- exact invocation/operation/application identities;
- operation absent/pending/conflicting/malformed;
- already-applied exact operation;
- completed receipt exactness;
- terminal missing receipt -> recovery required;
- successor checkpoint exactness;
- account tip/lineage mismatch blocks;
- duplicate D9 calls are read-only and deterministic;
- no effect gate assignment or effect boundary is reachable.

### Model routing

Security/read-authority/lineage/recovery-sensitive: **Sol High**.

## 7. D9-B — final D8/D9 source certification

D9-B begins only after exact D8-A, D8-B, and D9-A source reviews are accepted and the source tree is otherwise final for this settlement milestone.

Run focused regression surfaces first, including:

- new D8/D9 tests;
- finalized-decision storage/discovery tests;
- selected-C3/history/open-binding tests;
- Architecture-94 plan completion compatibility tests;
- PD4-C startup qualification tests;
- PD4-D unattended execution tests;
- Architecture-67 operation/receipt/account-lineage tests directly touched by shared contracts.

Then run one broad repository suite on the exact final unchanged D8/D9 source tree, plus Ruff and diff checks.

Do not rerun the broad suite for later docs-only certification records.

## 8. Protected D8-A real-host qualification

Real-host D8-A is not eligible until:

1. D7 first publication has been accepted from independent D7-D reconciliation;
2. that decision's intended execution session `E` has completed;
3. exact selected C3(E) exists under current C1;
4. exact accepted D8/D9 source/runtime identities are preflighted;
5. all eight gates are closed.

Under non-admin `DESKTOP-I4DOKM7\Trading`, run only the read-only D8-A production qualification.

Acceptance requires exact decision/C3/open/plan/startup evidence and no effect.

If result is `ALREADY_APPLIED`, do not execute again; proceed to D9-A reconciliation.

If result is `RECEIPT_RECOVERY_REQUIRED`, stop.

## 9. Protected D8-B first unattended settlement

D8-B requires separate explicit operator approval after a current successful D8-A qualification.

Run exactly one zero-semantic-argument D8-B production invocation under the non-admin Trading token.

Expected effect envelope:

```text
only unattended-execution gate opens process-locally
all other seven gates remain false
at most one existing unattended execution-composition call
no provider call
no decision publication
no storage provisioning
no receipt recovery
no scheduler mutation
no broker/live effect
```

Any ambiguous or abnormal result is STOP evidence. Do not rerun automatically.

## 10. Protected D9-A reconciliation

After D8-B, with all gates closed and in a fresh Trading process, run D9-A.

D8/D9 is accepted only if D9-A independently returns exact successful durable reconciliation.

A successful D8-B return by itself is never enough.

If D9-A reports receipt recovery required, stop and preserve durable evidence. No recovery is authorized by this plan.

## 11. Stop conditions

Stop and require review on at least:

```text
source/tree mismatch
unexpected worktree mutation
unexpected gate state
Trading token/C1 drift
finalized-decision ambiguity
selected-C3 provenance mismatch
verified-open contradiction
final-plan mismatch
Paper-v2 predecessor mismatch
invocation staging/conflict/malformed state
A67 conflicting/unknown state
terminal missing receipt
account successor/lineage mismatch
second execution attempt
any provider/publication/provisioning/scheduler/recovery/broker/live side effect
```

No stop condition authorizes cleanup, backfill, repair, a new operation identity, or automatic retry.

## 12. Acceptance record

The D8/D9 completion record should capture at least:

```text
accepted source commit/tree
focused test commands/results
final broad suite result
production interpreter/source preflight
Trading principal identity
current C1 authority epoch
finalized decision ID
selected decision/execution sessions and snapshot IDs
verified-open evidence summary
final-plan ID/digest
Paper-v2 predecessor checkpoint
expected invocation/operation/application IDs
D8-A classification
D8-B classification / real_effect_performed
D9-A reconciliation classification
receipt/final successor checkpoint
current account tip/lineage proof
all gates closed after effect
proof no prohibited effect occurred
```

Never record credentials, tokens, private keys, raw secret-store values, or reusable process-local authority.

## 13. Next milestone after D8/D9

After first settlement acceptance, update canonical status/handoff before proceeding.

The next protected operational milestone is **D10 bounded unattended simulated-paper soak**. Before D10 begins, freeze a concrete soak duration or number of successful cycles, explicit stop/escalation rules, and the scheduler-composition change required to move beyond the current D5 capture-only task.

Only after accepted D10 soak does the next major product milestone become **PD5 broker-paper integration**.
