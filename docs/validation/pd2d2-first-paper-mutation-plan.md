# PD2D2 First Paper Mutation — Validation Plan

## Scope and authorization state

This plan freezes the source, review, execution, interruption, and readback
workflow for Architecture 106. PD2D2-A is documentation only. It does not enable
an effect gate, run the executor, mutate Paper-v2, authorize provider call #7,
or authorize PD2D2-D.

The fixed source baseline immediately before PD2D2 architecture work is:

```text
HEAD: 7a643a1f88b1b15b8422709b8c8720670a681ac3
TREE: 695ca8d4c297eb4833ddc07adf321f47e3f16967
publication freeze blob: b125cbb1c80a827f74018cf2955b9a27ba69fa90
gates: (False, False, False)
status: clean
```

## Frozen source workflow

```text
PD2D2-A  accept Architecture 106 and this plan; effects remain disabled
PD2D2-B  implement and source-test the one-shot harness; effects remain disabled
PD2D2-C  review a separate one-line supervised gate enablement; do not execute
PD2D2-D  obtain fresh user approval and invoke exactly once as Trading
PD2D2-E  separately re-disable the gate, then perform read-only reconciliation
```

No phase automatically advances into PD2D2-D.

## PD2D2-B one-shot production harness

The future harness must:

- accept zero positional arguments and zero semantic options;
- embed the exact Architecture-106 operation identities and F1/F2 inputs as
  source-owned constants;
- require the publication freeze blob to remain
  `b125cbb1c80a827f74018cf2955b9a27ba69fa90`;
- require the production and recovery gates to be exactly `False`;
- require the supervised execution gate to be exactly `True` before any future
  real invocation;
- obtain genuine C1 authority and genuine P2 evidence for the exact selected
  provider call #6 snapshot without making another provider call;
- call only the public
  `execute_supervised_personal_desktop_paper_operation(...)` boundary;
- make exactly one such call and contain no retry loop or automatic recovery
  path;
- reconcile the exact frozen operation ID and application ID;
- treat only `COMPLETED/COMPLETED` with both evidence flags true and non-null
  cycle-result/successor IDs as exit-zero success;
- use a distinct nonzero exit for every non-normal result, exception, or
  reconciliation failure;
- emit one compact, sanitized evidence object only;
- omit raw filesystem paths, credentials, handles, C1/P2 capability objects,
  raw preparation/binding objects, and raw execution inputs; and
- provide no rerun path after interruption or ambiguous/no output.

The harness must have no semantic knob for strategy settings, idempotency,
timestamps, policies, metadata, historical configuration, seed artifact,
selection, plan, operation, application, root, executor, effect gate, retry, or
recovery.

## PD2D2-B source-only tests

All effects must be injected or faked. Tests must not invoke genuine
production/native/Paper-v2 mutation. Prove at minimum:

- the public command rejects every positional or optional semantic argument;
- the exact frozen production constants are constructed, including the seed
  hash/length and exact empty tuple inputs;
- all three gates are asserted in the required values;
- publication freeze identity is exact;
- genuine C1 and exact P2 call-#6 selection remain the production admission
  route;
- the supervised public execution boundary is called exactly once with the
  exact frozen inputs;
- no retry occurs after a returned failure or raised exception;
- exact operation/application result reconciliation is mandatory;
- only the complete normal result returns exit zero;
- `BLOCKED`, `CONFLICTING`, `ALREADY_APPLIED`, `EXECUTION_FAILED`,
  `RECEIPT_RECOVERED`, wrong identity, missing evidence, null required IDs, and
  exceptions each return a stable nonzero outcome;
- evidence output is compact and contains no paths, secrets, handles, authority
  objects, preparation/binding objects, or raw execution inputs;
- an interrupted or ambiguous invocation has no automatic rerun or recovery
  path;
- provider, broker, live, scheduler, account, ACL, LSA, KSP, credential, and
  security-state effects are absent.

Use disposable/private seams only. Never toggle the production source gate in
tests and never target `F:\AITradingBot\Paper-v2`.

Focused verification for PD2D2-B is limited to the new harness tests, the
existing PD2C boundary tests needed for shared composition, Ruff on changed
files, and `git diff --check`. A broad/full suite remains an explicit later
certification decision.

## PD2D2-C minimal gate checkpoint

PD2D2-C is a separate source review after PD2D2-B acceptance. Its intended
semantic diff is exactly:

```text
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
->
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = True
```

Requirements:

- no unrelated source or documentation change;
- production and recovery gates remain `False`;
- publication freeze blob remains unchanged;
- focused source/static checks pass;
- ChatGPT/Sol reviews the exact diff;
- no execution occurs during implementation, testing, commit, push, or source
  review;
- gate-enabled source acceptance still does not authorize PD2D2-D.

## PD2D2-D one-shot operator gate

Before execution, freeze and review the exact zero-argument command and confirm
the shell is the dedicated non-elevated
`DESKTOP-I4DOKM7\Trading` principal. Reconfirm the exact source commit/tree,
clean status, publication freeze, two disabled publisher/recovery gates, enabled
supervised gate, and the recorded PD2D1 READY evidence.

Then obtain fresh explicit user approval. That approval authorizes exactly one
invocation of the reviewed command, not a retry, recovery, provider call, broker
call, or any other effect.

Expected exit-zero evidence is exactly the normal Architecture-106 result:

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

Any other result, exception, nonzero exit, interruption, lost shell, missing
output, or ambiguous output is a STOP. Do not rerun.

## Interruption handling

After an interrupted or ambiguous PD2D2-D attempt:

1. do not rerun, repair, recover, rename, or delete any durable object;
2. perform no additional effectful inspection under the enabled source;
3. prepare and review PD2D2-E's minimal `True -> False` source change;
4. close the gate; and
5. only then run the separately reviewed read-only reconciliation.

Any recovery action or second execution requires a new explicit review and
authorization.

## PD2D2-E gate closure and readback

PD2D2-E first changes only the supervised gate from `True` back to `False` in a
separate reviewed source checkpoint. The publisher and recovery gates remain
`False`, and the publication freeze remains unchanged.

After that checkpoint is active, the reviewed read-only verification must use
existing C1, Paper-v2 reader, lineage, transition, receipt, and Architecture-67
inspection contracts to prove the Architecture-106 post-mutation conditions:

- genuine C1 and genuine Paper-v2 account reread pass;
- GENESIS remains a valid ancestor;
- normal success advances the terminal exactly one edge;
- returned result/successor IDs reconcile to the committed report/checkpoint;
- the frozen operation inspects as `ALREADY_APPLIED` after normal success;
- its exact receipt verifies;
- no staging objects remain after normal success;
- no second transition or receipt exists; and
- all three gates are `False`.

For an abnormal/ambiguous attempt, preserve and report the exact read-only
classification instead of forcing the normal-success assertions. Do not add
repair logic.

## Acceptance boundaries

```text
PD2D2-A acceptance != PD2D2-B/C source authorization
PD2D2 source acceptance != Paper-v2 mutation authorization
gate-enabled source review != PD2D2-D authorization
PD2D1 READY evidence != reusable execution authority
```

Fresh explicit user approval immediately before PD2D2-D is mandatory.
