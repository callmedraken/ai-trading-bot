# PD4 Unattended Decision Publication Validation Plan

Status: frozen validation plan for Architecture 113. Source work only until an explicitly approved protected D7 checkpoint. This plan does not authorize a real decision publication, storage provisioning, Paper-v2 mutation, scheduler mutation, broker effect, or live effect.

## 1. Objective

Validate the Architecture-113 D6 decision-only production composition around the repository's existing G4 decision-intent, fixed storage, pre-open permit, and hardened output primitives, then separately validate one protected first real D7 publication when the authoritative C3 warm-up naturally reaches an eligible `DECISION_READY` state.

The plan must preserve the armed D5 capture-only scheduler and worktree unchanged while D6/D7 source work occurs on the isolated feature branch/worktree.

## 2. Fixed source/deployment separation

During D6 source development:

```text
armed D5 branch/worktree = unchanged
installed D5 task         = unchanged
all committed effect gates = False
D6 source/tests            = isolated branch/worktree only
real decision publication  = not authorized
```

No D6 source checkpoint may modify the currently armed D5 scheduler action or invoke the D5 provider path.

## 3. D6-A — architecture and test contract freeze

Accept D6-A only when:

- Architecture 113 is present and reviewed;
- this validation plan is present and reviewed;
- G4 existing primitives have been confirmed rather than reimplemented;
- the production composition explicitly uses independent source-owned re-derivation rather than a G6 public result;
- the existing PD2A account mutex covers predecessor-sensitive construction/publication reconciliation;
- fresh publication is defined as `ABSENT -> one permit -> at most one publish -> fresh FINALIZED_IDENTICAL`;
- `FINALIZED_IDENTICAL` is zero-write convergence;
- decision storage provisioning is separated from D6 publication;
- D7 remains a protected effect checkpoint.

No runtime effect occurs in D6-A.

## 4. D6-B — bounded source implementation

Implement only the Architecture-113 composition and launcher required for D6.

Expected implementation characteristics:

```text
zero-semantic-argument D6 launcher
all-eight-closed initial gate admission
strict pre-lock account qualification
existing PD2A mutex acquisition
strict post-lock account reread
current-C1 selected-C3/history decision reconstruction
fixed decision-storage read
strict pre-open qualification
process-local decision-publication gate only
one permit / one writer / one publish budget
finally-close publication gate
fresh all-gates-closed decision-storage reread
final account predecessor reread under held mutex
bounded non-authorizing public result
```

Do not redesign existing intent/storage/permit/writer schemas or deterministic identities unless implementation exposes a concrete contradiction requiring a new architecture review.

Do not modify:

- D5 scheduler contract/action;
- D5 armed source worktree;
- market-data capture authority;
- Paper-v2 execution/recovery authority;
- storage provisioning authority except for import/reuse needed by read-only qualification;
- broker/live boundaries.

Because D6 implements Windows/security/authority/order/crash-sensitive production composition, delegated implementation should use Sol High rather than Luna/Astra unless the architecture is later narrowed to a purely mechanical correction.

## 5. D6-C — focused source verification

Run focused tests before any broad certification. At minimum cover:

### Invocation and gate containment

- parser/launcher accepts no semantic trading arguments;
- each of the eight gates independently blocks if initially open/non-boolean;
- only decision-publication gate is true inside the exact native writer call;
- all seven companion gates remain false;
- publication gate is restored false on success, no-op, and exception paths;
- committed gate constants remain false.

### Re-derivation and account serialization

- G6 public result is never publication authority/input;
- no G5/provider path is reachable;
- exact C1/account/selected-C3/history/strategy decision is independently reconstructed;
- strict account read occurs before lock;
- strict account truth is reread after lock;
- same PD2A mutex is held through final post-publication account reread;
- predecessor drift prevents clean success acceptance.

### Storage/deadline/duplicate behavior

- only genuine production `ABSENT` can mint a fresh permit;
- `FINALIZED_IDENTICAL` returns zero-write convergence;
- finalized-identical does not issue a fresh permit/open a writer/open the effect gate;
- staging, conflicting, malformed, unknown, security-drift, or reparse state blocks;
- before-open admission works;
- at/after-open maps to `MISSED_DECISION_DEADLINE` and performs no write;
- duplicate concurrent/repeated invocations converge deterministically without duplicate durable publication.

### One-shot/crash semantics

- at most one permit is issued per invocation;
- at most one writer is opened per invocation;
- `publish()` is called at most once;
- write/flush/finalization/readback failure spends the permit;
- no same-invocation retry occurs;
- staging/ambiguous durable state is not automatically deleted/repaired;
- a later invocation may reconsider publication only after a complete fresh read proves exact `ABSENT` and the deadline/admission remain valid.

### Post-publication authority

- writer success alone is insufficient;
- after all gates are closed, fresh production storage reread must prove exact `FINALIZED_IDENTICAL`;
- final C1/session/decision/account predecessor bindings are exact;
- public result exposes no permit, capability, handle, credential, path authority, or raw production-authority object;
- `real_effect_performed` is accurate and diagnostic only.

### Prohibited effects

Focused tests must prove D6 cannot:

- capture market data;
- execute/recover Paper-v2;
- provision/repair storage;
- mutate Task Scheduler;
- submit broker orders;
- enter live trading.

No focused source test may require a real provider call, real Paper-v2 mutation, scheduler mutation, broker effect, or live effect.

## 6. D6-D — exact diff and final source certification

Before broad certification:

1. inspect exact changed-file set;
2. confirm no unrelated generated/untracked artifacts were staged or modified;
3. confirm armed D5 files/worktree/scheduler contract are untouched;
4. review the exact source diff against Architecture 113;
5. run repository formatting/lint/type/static checks required by current project policy;
6. run the complete repository suite once on the final unchanged D6 source tree.

If broad certification fails, diagnose and correct only the affected area, rerun focused verification, then rerun the broad suite only when the final tree is ready for certification.

D6 source acceptance still leaves every committed production effect gate false and does not authorize D7.

## 7. D7-A — protected real-host read-only qualification

D7 may be considered only when the D5 authoritative warm-up naturally reaches a current candidate decision with sufficient consecutive selected-C3 history and the publication deadline is still open.

Under the non-admin `DESKTOP-I4DOKM7\Trading` production token, perform read-only qualification of:

```text
exact accepted D6 source commit/tree
production interpreter/runtime contract
current C1 authority
exact Paper-v2 account identity/predecessor
current selected C3 session and lineage
required consecutive selected-C3 history
exact deterministic candidate decision
intended execution session E
regular_open(E) and current strict-before-open eligibility
fixed unattended decision namespace
namespace owner/ACL/reparse/identity expectations
current storage classification
all eight gates closed
```

D7-A performs no decision publication and no storage mutation.

Any contradiction or missed deadline stops the checkpoint.

## 8. D7-B — conditional storage provisioning only if missing

If and only if D7-A proves the fixed decision namespace is absent and the existing storage-provisioning architecture says provisioning is required, stop publication qualification.

A separate explicit operator approval is required for the existing Administrator storage-provisioning effect.

After provisioning:

1. close the provisioning effect boundary;
2. return to non-admin `Trading`;
3. repeat the complete D7-A read-only qualification from fresh durable state.

Provisioning does not itself authorize publication.

If the namespace already exists and fully reconciles, skip D7-B.

## 9. D7-C — first protected real decision publication

D7-C requires explicit operator approval after a successful current D7-A/D7-B qualification.

Run exactly one zero-semantic-argument D6 production invocation under the non-admin `Trading` token.

Acceptance expectations:

```text
publication begins only from exact ABSENT
observed_now remains strictly before regular_open(E)
only decision-publication gate opens process-locally
at most one native publication attempt occurs
all other seven gates remain false
publication gate closes in finally
no provider/Paper-v2/storage-provisioning/scheduler/broker/live effect occurs
```

If the deadline has passed, do not run or repeat a publication attempt for that execution session.

If the invocation becomes ambiguous or leaves staging/conflicting state, stop. Do not clean, repair, delete, rename, overwrite, or retry automatically.

## 10. D7-D — independent post-publication reconciliation

After D7-C, with all eight gates closed and under a fresh non-admin `Trading` process, independently verify:

```text
exact finalized decision exists
storage classification == FINALIZED_IDENTICAL
canonical bytes/digest/decision ID are exact
current C1 binding is valid
intended execution session is exact
account predecessor still equals the predecessor bound into the intent
Paper-v2 account state was not mutated by D7-C
no market-data capture occurred
no scheduler/storage-provisioning/broker/live effect occurred
```

A successful D6 process exit alone is not acceptance evidence.

D7 is accepted only from fresh durable reconciliation.

## 11. Stop conditions

Stop and require architecture/operator review on at least:

```text
source/tree mismatch
worktree mutation
unexpected gate state
C1 drift or ambiguity
account/predecessor mismatch
selected-C3/history contradiction
SESSION_GAP
MISSED_DECISION_DEADLINE
STAGING_PRESENT
CONFLICTING/malformed/unknown storage
security/reparse/parent identity drift
PUBLICATION_OUTCOME_AMBIGUOUS
unexpected writer reuse or second publication attempt
any market-data/Paper-v2/scheduler/broker/live side effect
```

No stop condition authorizes cleanup, backfill, repair, retry, or a broader effect boundary.

## 12. D6/D7 acceptance record

The milestone record must capture at least:

```text
accepted source commit and tree
focused test commands/results
broad suite command/result
real-host production interpreter identity
production user identity
current C1/authority epoch identity
candidate decision ID and execution session
predecessor checkpoint identity
selected-C3/history evidence summary
publication deadline evidence
pre-publication storage classification
whether provisioning was required
publication invocation classification
real_effect_performed
post-publication FINALIZED_IDENTICAL evidence
proof all gates closed after invocation
proof account state was not mutated
proof no prohibited effect occurred
```

Do not record credentials, private keys, tokens, raw secret-store values, or reusable process-local authority.

## 13. Next milestone after D7

After D7 acceptance, update canonical status/handoff documents before proceeding.

The next architecture checkpoint is D8/D9 composition: consume a finalized pre-open decision targeting execution session `E` only after the current-C1 selected C3 snapshot for `E` exists, bind exact verified `open(E)`, construct the existing Architecture-94 final plan, and enter the reviewed Architecture-110/67 Paper-v2 reconciliation path.

That later work must remain separate from Architecture 113. D6/D7 does not open unattended Paper-v2 execution/recovery authority and does not modify the D5 scheduler into a combined trading cycle.
