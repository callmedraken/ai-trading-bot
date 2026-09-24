# Architecture 122 — One-Week Bounded Unattended Simulated-Paper Soak Authority

Status: frozen D10 design checkpoint. This document does not authorize scheduler mutation or recurring effects.

## Scope and operator decision

Run unattended simulated Paper-v2 for exactly one calendar week from accepted activation, then stop and re-evaluate.

The soak is evidence gathering only. It does not automatically graduate the project to broker-paper.

Duration policy:
- 7 calendar days from accepted activation.
- No automatic extension.
- No automatic graduation.
- Paper-v2 only; broker-paper and live remain unavailable.

## Controlling contracts

Architecture 122 composes Architectures 77/82, 94, 102-114, 121, and the Architecture-111 two-phase daily cycle without weakening them.

The scheduler remains a zero-semantic-argument wake-up source. C3 remains the unattended daily-bar authority. Decision publication and Paper-v2 execution remain separately gated. Receipt recovery remains separately authorized. No missed session may become an automatic multi-session catch-up.

## One-week window

Deployment must prove the activation instant, end instant equal to activation plus seven calendar days, exact source HEAD/TREE, Trading principal SID, production Python identity, and scheduler contract identity.

The scheduled D10 task must not produce effectful wakes after the end boundary. If the end boundary cannot be enforced deterministically, deployment stops rather than relying on manual disablement.

## One wake

A normal wake may perform at most this ordered sequence:

1. Fresh C1, Trading token, source and gate validation.
2. Source-derived completed-session C3 capture if required.
3. Close the market-data gate.
4. Read-only daily-cycle reconstruction.
5. Settle at most one finalized decision targeting the exact current completed session, if eligible.
6. Close the unattended-execution gate.
7. Independent all-gates-closed settlement reconciliation.
8. Independently reconstruct the next pre-open decision.
9. Publish at most one exact decision only while its pre-open deadline remains valid.
10. Close the decision-publication gate.
11. Independent all-gates-closed decision reconciliation.
12. Emit bounded soak evidence.

Every stage re-reads source-owned durable truth. An effect result never becomes authority for the next effect.

Per-wake fresh-effect budgets:
- C3 provider attempt: at most one.
- Paper-v2 settlement attempt: at most one.
- Decision publication attempt: at most one.
- Receipt recovery attempts: zero.
- Historical catch-up loops: zero.
- Broker/live calls: zero.

## Late wakes and stale state

A late wake may continue only when ordinary source-derived session and pre-open rules still hold.

If the next intended decision deadline has passed and no exact decision was finalized, return MISSED_DECISION_DEADLINE and stop the soak. Do not create the missed decision later.

Historical finalized decision artifacts are retained after successful settlement, so their mere presence is not stale state.

D10 must distinguish already-reconciled historical decisions from an unresolved prior-session decision. Before any new settlement or publication effect, it must prove that every finalized decision older than the current completed session is already durably converged: exact invocation storage is finalized-identical, the expected Architecture-67 operation is already applied, the completed receipt verifies, and the Paper-v2 lineage contains the exact deterministic successor.

If any prior finalized decision is not independently proven reconciled, classify STALE_UNRESOLVED_DECISION, stop the soak, and require operator review. Ordinary D10 must not settle that prior decision. Architecture 121 is not automatically reused.

If history or durable state implies more than one trading session would require retrospective fresh work, return SESSION_GAP and stop. Do not synthesize, skip, or backfill.

## Duplicate wake, restart, and overlap

Scheduler overlap controls are defense in depth. Authoritative duplicate safety remains current-C1 reconstruction, durable decision storage, PD2A mutex, Architecture-67 deterministic identities, invocation storage, receipts, and account lineage.

A restarted or duplicate process may observe already-completed durable work and return an idempotent/read-only classification. It may not derive retry authority from the previous process result.

## Stop conditions

Stop the soak for operator review on BLOCKED, SESSION_GAP, MISSED_DECISION_DEADLINE, provider attempt ambiguity, RECEIPT_RECOVERY_REQUIRED, STALE_UNRESOLVED_DECISION, conflicting or malformed durable state, account predecessor/tip/lineage contradiction, C1 or Trading-token drift, effect-gate drift, unexpected scheduler/source identity, an ambiguous effect result, or a source upgrade during the active soak.

A stop condition does not restart or extend the seven-day window automatically.

## Evidence

Every wake must emit bounded operator-readable evidence for source/runtime identity, observed time and completed session, capture state, decision identities, plan/invocation/operation/application identities, checkpoint identities, reconciliation state, effect crossings, final closed-gate proof, and any stop reason.

Evidence must not expose credentials, raw authority objects, reusable capabilities, or native handles.

## End-of-week review

At the seven-day end boundary, recurring D10 effect authority closes before review.

Review scheduled wakes, eligible XNYS sessions, captures, publications, settlements, independent reconciliations, no-effect/idempotent wakes, all stop or ambiguity events, provider/network behavior, sleep/reboot/duplicate-wake observations, Paper-v2 positions/trades/performance, and audit completeness.

The review may accept PD4 operational evidence, extend simulated-paper under a new bounded authorization, correct and repeat, or remain in simulated paper. It may not automatically enable broker-paper.

## Source/deployment separation

Source implementation and certification come before scheduler mutation. The existing capture-only task remains unchanged until a later explicit D10 deployment approval.

## Acceptance criteria

Tests must prove zero semantic scheduler arguments, an exact seven-day bound, source-owned session derivation, ordered effect/reconciliation composition, one-attempt limits, finally-restored gates, stale-unresolved/missed/session-gap fail-closed behavior, diagnostic-only receipt recovery, duplicate/restart convergence, no broker/live path, sanitized evidence, and unchanged Architecture-111/114/121 semantics.

## Exit

After one calendar week, stop and re-evaluate. Elapsed time alone authorizes no next trading mode.


## Runtime activation-lease authority

Source review of the first D10 checkpoint exposed a required authority boundary
before the recurring controller can be implemented: the zero-argument runtime
must be able to prove the seven-day activation/end interval without trusting a
scheduler wake, scheduler history, a caller argument, ambient environment, or
process memory.

The Task Scheduler end boundary remains required as defense in depth, but it is
not sufficient authority by itself.

Architecture 122 therefore requires one fixed source-owned D10 activation lease.
The lease is created only at the later explicitly approved D10 deployment
checkpoint and is read-only to the scheduled controller.

Required lease facts are:

- schema/version;
- accepted activation UTC instant;
- exact end UTC instant equal to activation plus seven days;
- exact certified source HEAD and TREE;
- exact D10 scheduler-contract identity/version;
- exact Trading SID;
- exact production Python identity/version;
- a unique D10 soak identity derived deterministically from the canonical lease
  facts.

The lease location, ACL/ownership contract, atomic create/finalize behavior,
canonical serialization, native-safe read path, and deployment writer must be
source-frozen before D10 scheduler mutation.

The scheduled controller accepts no lease facts from CLI arguments or
environment variables. On every wake it must independently read and verify the
fixed lease, compare current UTC time against the lease interval, and perform no
effect when the lease is absent, malformed, conflicting, not yet active, or
expired.

The lease is not renewable in place. Extending the soak requires a new reviewed
bounded authorization after the current week is closed.


## Deployment identity prerequisite

The activation-lease implementation correctly stopped because the repository
had no runtime-verifiable mapping from certified Git HEAD/TREE to deployed
executable bytes without trusting `.git`.

Architecture 123 is therefore a mandatory predecessor. D10 runtime authority
requires the fixed detached-signed deployment attestation and complete
executable-file manifest defined there. The activation lease binds the verified
deployment ID and attestation digest; HEAD/TREE strings alone are never runtime
authority.


## Architecture 124 launch-contract revision

The original D10 scheduler target that pointed directly at the source-tree
launcher is superseded before any production deployment.

The final D10 scheduler must invoke the fixed sealed pre-source guard defined by
Architecture 124:

```text
F:\AITradingBot\runtime\python.exe
-I -S -B
-X pycache_prefix=F:\AITradingBot\D10\no-pycache
F:\AITradingBot\D10\launch-guard.py
```

The guard, not Task Scheduler, verifies deployment identity and ACTIVE lease
state before launching the sealed second-stage D10 source.

The deployed trading source root is fixed at
`F:\AITradingBot\D10\source`; recurring D10 authority no longer runs from a
mutable Git worktree.
