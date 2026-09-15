# Architecture 113 — Personal-Desktop Unattended Decision Publication Authority

Status: frozen PD4-D6/D7 source-design checkpoint; documentation only; no decision publication, storage provisioning, Paper-v2 effect, scheduler mutation, broker effect, or live effect is authorized by this document.

## 1. Scope and decision

Architecture 113 defines the production composition required to turn an Architecture-111 effects-closed `DECISION_READY` condition into at most one durable pre-open unattended decision publication.

The repository already contains the required G4 primitives: the canonical `PersonalDesktopUnattendedPaperDecisionIntent`, fixed decision-storage reader, `PreOpenDecisionPublicationPermit`, publication qualification, and hardened `PersonalDesktopPaperRuntimeUnattendedDecisionOutputCapability`. Architecture 113 does not redesign those primitives. It freezes how production may compose them.

The central decision is:

> D6 is a zero-semantic-argument decision-only production boundary. It independently re-derives the exact source-owned account, selected-C3, history, strategy, deadline, C1, and storage facts; holds the existing PD2A account mutex across the final predecessor-sensitive decision construction and publication reconciliation; opens only the decision-publication effect gate process-locally for at most one writer/publish attempt; closes that gate in `finally`; and accepts success only after a fresh all-gates-closed storage reread proves the exact finalized decision while the account predecessor still matches.

A G6 public result is diagnostic evidence only. It is never publication authority and is not an input to D6.

Architecture 113 does not authorize a real D7 publication. It also does not authorize storage provisioning, market-data capture, Paper-v2 execution or recovery, Task Scheduler mutation, broker-paper submission, or live trading.

## 2. Controlling predecessor contracts

Architecture 113 composes and must not weaken:

- Architectures 77/82 C2/C3 transactional market-data, crash/recovery, selection, and at-most-once authority;
- Architecture 94 selected-C3 and deterministic strategy-plan authority;
- Architecture 102 dedicated non-admin `Trading` security profile;
- Architectures 103–109 Paper-v2 account, mutex, execution, reconciliation, mutation, and recovery authority;
- Architecture 110 zero-semantic-argument unattended invocation, scheduler-as-wakeup-only, PD2A mutex, and effects-closed composition rules;
- Architecture 111 pre-open decision intent, deadline, rolling selected-C3 history, session-gap, and separate decision-publication-gate authority;
- Architecture 112 capture-only D5 warm-up separation;
- the existing fixed unattended decision namespace and hardened G4 storage/output contracts.

No G6 result, scheduler metadata, wall-clock wake identity, filesystem discovery, filename ordering, caller-supplied session, mutable cache, process exit code, or process lifetime may replace durable/source-owned authority.

## 3. D6 boundary and zero-semantic-argument rule

D6 is a distinct production entry point. Its launcher accepts no semantic trading arguments.

The wake may not supply:

```text
account ID
symbol/universe
selected snapshot or selection ID
decision ID
execution session
market-data session
history seed
strategy parameters
publication path
storage root
observed deadline override
retry count
effect flag
provider or broker identity
```

All such facts are source-owned or derived from current durable authority.

D6 must not call G5, construct provider authority, open the market-data gate, or depend on the D5 capture launcher. D5 and D6 remain separate effect boundaries.

## 4. Initial gate admission

D6 may begin only when all eight committed production effect gates are exact booleans and false:

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

Any open or non-boolean gate is `BLOCKED` before publication qualification.

The committed source value of every gate remains `False`.

## 5. Independent source-owned re-derivation

D6 must not consume a prior G6 result as authority. It independently performs the current production reads needed to reconstruct the exact next-decision facts under the current C1 authority.

At minimum it must reconcile:

```text
current C1 production authority
exact Paper-v2 account identity and predecessor
current selected C3 decision session
required consecutive selected-C3 strategy-history binding
source-owned unattended profile
MovingAverageCrossoverConfig(short_window=3, long_window=5, desired_quantity=1)
exact strategy/decision evidence
intended execution session E = next_session(current decision session)
regular_open(E)
fixed unattended decision-storage state
```

Any contradiction, gap, stale provenance, ambiguous durable state, or unsupported authority blocks rather than falling back to an offline seed, caller input, or filesystem discovery.

## 6. PD2A mutex and predecessor-sensitive publication transaction

The canonical unattended decision intent binds the Paper-v2 predecessor checkpoint. A concurrent account mutation during decision construction/publication could therefore make a newly finalized decision stale.

D6 reuses the existing PD2A account mutex. The mutex grants no Paper-v2 mutation authority; it only serializes predecessor-sensitive reconciliation.

Required ordering:

```text
strict pre-lock account identity/read-only qualification
-> acquire existing PD2A account mutex
-> strict post-lock account reread
-> derive exact selected-C3/history/strategy decision under current C1
-> read fixed decision storage
-> perform deadline/admission qualification
-> if eligible, perform at most one publication attempt
-> restore all gates closed
-> fresh production decision-storage reread
-> final account predecessor reread while mutex is still held
-> final C1/gate reconciliation
-> release mutex
```

If post-lock account truth differs from pre-lock assumptions, D6 recomputes from the post-lock truth or blocks according to the existing deterministic contract. It must not publish an intent bound to a predecessor that is no longer current.

After publication, if the account predecessor no longer equals the predecessor bound into the exact finalized intent, the invocation is not accepted as a clean publication outcome. No automatic repair, deletion, or replacement publication is authorized.

## 7. Storage admission and duplicate convergence

The fixed production decision namespace remains the existing source-owned location:

```text
F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

D6 uses only the existing hardened production storage reader and its provenance.

Fresh publication is possible only from genuine production storage classification:

```text
ABSENT
```

The exact fresh-path rule is:

```text
ABSENT
-> issue one pre-open permit
-> open at most one writer
-> call publish at most once
-> close decision-publication gate
-> fresh reread must prove FINALIZED_IDENTICAL
```

`FINALIZED_IDENTICAL` is zero-write convergence. It must not mint a new permit, open a writer, reopen the effect gate, rewrite bytes, or refresh publication time.

`STAGING_PRESENT`, `CONFLICTING`, malformed/unknown state, parent/security drift, reparse state, or multiple durable candidates are `BLOCKED` unless an existing lower-level contract already supplies a more conservative classification.

## 8. Strict pre-open deadline authority

A new decision may be published only when:

```text
observed_now < regular_open(E)
```

The deadline must be checked by the existing source-owned timing/publication qualification before a fresh permit is issued and must still hold at the writer/publication boundary required by the existing G4 contract.

At or after `regular_open(E)`:

```text
MISSED_DECISION_DEADLINE
```

No late wake may manufacture a fresh decision for `E`, and no historical catch-up publication is authorized.

Wall-clock observation is admission evidence only. It is not part of deterministic decision identity or canonical artifact bytes.

## 9. One-shot permit and writer rule

A production `PreOpenDecisionPublicationPermit` is:

- bound to the exact decision/storage/C1 production provenance;
- same-process;
- non-copyable;
- non-serializable/non-picklable;
- one-shot;
- consumable by at most one native publication attempt.

One D6 invocation has a publication-attempt budget of one.

There is no read-only writer probe followed by an effectful second writer. There is no second permit or second `publish()` call after write, flush, finalization, readback, or other publication failure.

Process exit, exception, launcher retry, or scheduler history never grants retry authority.

## 10. Decision-publication gate isolation

Only after all qualification succeeds may D6 temporarily change the process-local decision-publication gate to true.

During the native writer call:

```text
decision publication       = True
market-data capture        = False
Paper-v2 production        = False
Paper-v2 recovery          = False
supervised execution       = False
receipt recovery           = False
unattended execution       = False
storage provisioning       = False
```

D6 must restore the decision-publication gate to false in `finally`.

No companion gate may be assigned or opened by D6.

The existing hardened writer remains responsible for fixed-path validation, security/identity checks, exclusive staging, canonical exact bytes, durable write/flush behavior, no-clobber same-parent finalization, and exact final reread.

## 11. Post-publication acceptance is durable reread, not return value

A successful `publish()` return is not sufficient acceptance evidence.

After the gate is closed and all eight gates are reverified false, D6 must perform a fresh production storage read and accept `DECISION_PUBLISHED` only when durable authority proves the exact expected decision is `FINALIZED_IDENTICAL`, including the existing canonical identity/bytes/digest/session/C1 bindings.

While the PD2A mutex is still held, D6 then performs a final strict Paper-v2 account reread. The current predecessor must still equal the predecessor bound into the finalized decision intent.

Final acceptance therefore requires:

```text
all gates closed
exact finalized decision durably reconciled
current C1 still valid
execution session binding unchanged
account predecessor unchanged under held mutex
```

The public result contains no reusable permit, capability, native handle, path authority, credential material, or raw production-authority object.

## 12. Crash and ambiguity semantics

Architecture 113 follows durable-state-first recovery.

If an invocation fails or terminates before publication is durably known, a later new wake begins from a completely fresh production reconciliation. The previous process exit code or in-memory state has no authority.

A later new wake may consider another fresh publication only when all of the following are independently true:

```text
production decision storage == exact ABSENT
publication deadline is still open
current C1/account/selected-C3/history/decision facts all reconcile
all eight gates are initially closed
```

If durable staging exists:

```text
STAGING_PRESENT -> BLOCKED
```

No automatic delete, rename, overwrite, repair, or same-invocation retry is authorized.

If the final artifact exists and is exact:

```text
FINALIZED_IDENTICAL -> zero-write convergence
```

If durable state is conflicting, malformed, unknown, or cannot be safely classified, D6 reports `BLOCKED` or `PUBLICATION_OUTCOME_AMBIGUOUS` according to the evidence available. Such a result does not itself authorize cleanup or retry.

## 13. Public classifications

The D6 public boundary must be able to distinguish at least:

```text
DECISION_NOT_READY
DECISION_PUBLISHED
DECISION_ALREADY_FINALIZED
MISSED_DECISION_DEADLINE
SESSION_GAP
PUBLICATION_OUTCOME_AMBIGUOUS
BLOCKED
```

Existing more-specific safe classifications may be preserved where useful.

`real_effect_performed` must reflect whether this invocation actually crossed the reviewed native publication effect boundary. It is diagnostic only and grants no later authority.

## 14. Storage provisioning is a separate protected checkpoint

Architecture 113 does not authorize D6 to create, repair, or alter the decision namespace.

Before the first real D7 publication, a separate read-only production-host qualification must verify the fixed decision namespace and its exact expected security/identity state.

If the namespace is absent, provisioning must use the already-reviewed unattended storage-provisioning authority in a separately approved Administrator checkpoint. After provisioning, the non-admin `Trading` account must perform a fresh read-only qualification before publication can be considered.

D6 never opportunistically provisions storage.

## 15. Prohibited effects

D6 must not:

- call G5 or perform any provider/market-data capture;
- open the market-data gate;
- execute or recover Paper-v2;
- open production/recovery/supervised/receipt/unattended Paper-v2 gates;
- provision or repair storage;
- modify Task Scheduler;
- alter the armed D5 launcher/worktree;
- submit broker orders;
- enter live-trading authority;
- perform multi-session catch-up or historical decision backfill.

## 16. Required source tests

Source acceptance must prove at least:

- zero semantic arguments;
- any initially open/non-boolean gate blocks;
- G6 public output is not consumed as authority;
- no G5/provider path is reachable;
- strict pre-lock and post-lock account reconciliation;
- the existing PD2A mutex covers decision construction through final post-publication account reread;
- exact current-C1 selected-C3/history decision reconstruction;
- fresh publication is possible only from `ABSENT`;
- `FINALIZED_IDENTICAL` converges with zero write and no fresh permit/writer;
- staging/conflict/malformed/unknown storage blocks;
- strict-before-open succeeds and at/after-open fails;
- only decision-publication gate is true during the exact writer call;
- all seven companion gates remain false;
- decision-publication gate closes after success, safe no-op, and exceptions;
- at most one permit, writer, and `publish()` call per invocation;
- publication failure never performs same-invocation retry;
- post-publication acceptance requires a fresh all-gates-closed `FINALIZED_IDENTICAL` reread;
- final account predecessor drift is detected before clean acceptance;
- public result exposes no reusable authority;
- committed source gate constants remain false;
- no test requires a real provider, Paper-v2 mutation, scheduler mutation, broker call, or live effect.

Focused failure-injection tests must cover at least staging creation, write/flush/finalization/readback failure seams exposed by the existing output capability and prove permit spending/no automatic repair semantics.

## 17. D7 protected first-publication sequence

Source acceptance does not authorize D7.

When the C3 warm-up reaches an exact current `DECISION_READY` condition and before that decision's `regular_open(E)`, the first real publication requires a separately reviewed operator checkpoint:

```text
D7-A  Trading read-only production qualification
      -> exact source/runtime/C1/account/selected-C3/history
      -> exact decision namespace/security state
      -> exact candidate decision and open deadline

D7-B  only if namespace is missing:
      separately approved Administrator provisioning
      -> fresh Trading read-only requalification

D7-C  explicit approval for one zero-semantic-argument D6 production invocation
      -> at most one decision-publication effect

D7-D  independent Trading read-only reconciliation with all gates closed
      -> exact FINALIZED_IDENTICAL decision
      -> no Paper-v2 account mutation
      -> no market-data/scheduler/broker/live effect
```

The first D7 acceptance does not require a scheduler action change. An operator wake is acceptable because the wake carries no semantic trading authority.

If the publication deadline is missed, the correct result is fail-closed. No retrospective publication/backfill is authorized.

## 18. Acceptance criteria

Architecture 113 is accepted when source and later protected D7 evidence prove:

```text
D6 is zero-semantic-argument and decision-only
G6 result is non-authorizing
D6 independently re-derives exact durable/source-owned state
PD2A mutex protects predecessor-sensitive construction/publication reconciliation
fresh publication begins only from exact ABSENT
strict pre-open deadline controls permit issuance/publication
one invocation has at most one permit/writer/publish attempt
only decision-publication gate opens process-locally
all gates close in finally
FINALIZED_IDENTICAL is zero-write convergence
post-publication durable reread, not writer return, controls acceptance
account predecessor remains exact through final reconciliation
ambiguous/staging/conflicting state fails closed without repair
storage provisioning remains separate
market-data, Paper-v2, scheduler, broker, and live effects remain prohibited
real D7 publication remains separately and explicitly authorized
```
