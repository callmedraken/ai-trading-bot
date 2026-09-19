# PD4 D7 Decimal Requalification Source Candidate

## Status and scope

**ACCEPTED — REPLACEMENT D7 SOURCE CERTIFICATION**

This record now closes the replacement source-certification boundary for the
D7-A/D7-D source after the Decimal determinism and frozen-seed checkout
corrections. It authorizes no production publication or other external effect.
Fresh D7-A remains read-only and D7-C remains protected and explicitly
unauthorized.

Certified replacement source:

```text
HEAD: acd606a41ac50f172ac62377ce6d4e7c8c4d3a32
TREE: 784695d05865a767ba187adf38fd4924897127a9
```

Certification:

```text
broad suite excluding Architecture-77: 5534 passed, 17 skipped
Architecture-77 clean-harness suite:    775 passed
combined:                               6309 passed, 17 skipped
Ruff check:                             PASS
Ruff format --check:                    PASS (532 files)
git diff --check:                       PASS
git diff --cached --check:              PASS
worktree/index:                         clean
origin HEAD:                            exact source HEAD
```

Both Architecture-77 test modules were byte-identical between this candidate
and the clean integration harness. Import proof showed the harness imported the
candidate source tree. No permission workaround or source mutation was used.

## Base D7 lineage

The candidate begins at the current remote D7 documentation tip:

```text
branch: feature/pd4-unattended-decision-publication
HEAD:   387497c7a662181d9a7e496026cf95ccdac998f5
TREE:   08c7ebdbd79b9d8b684b51e1733c2b162652ca7f
```

Its certified D7 source ancestor is:

```text
HEAD: 3dfa9e2cab372f8cb034b90256ed3fba9da6c878
TREE: bb1de2e7c2933ba3a777523f2a0e2feee5fa8c39
```

The four intervening commits are documentation-only. They record source
certification and the historical D7-A production qualification; they do not
change the certified D7 source implementation.

## Decimal root cause and compatibility-first correction

The D7 moving-average strategy performed `Decimal` average division and
canonical quantity normalization under the caller's ambient decimal context.
Hostile precision or rounding therefore could change proposal reason text,
proposal identity material, and downstream Architecture-94 plan bytes.

The correction preserves the existing D7 strategy shape and runs only the
existing average calculation and canonical `normalize()` rendering inside a
private fixed context with precision 28, `ROUND_HALF_EVEN`, `Emin=-999999`,
`Emax=999999`, `capitals=1`, `clamp=0`, and traps for `InvalidOperation`,
`DivisionByZero`, and `Overflow`. It does not port the later O4 evaluator types
or helper and does not alter namespace, UUID material order, quantity, reason,
position filtering, crossover, equality, or Decimal-subclass behavior.

The frozen bullish compatibility vector is:

```text
closes:           10, 10, 9, 12
short / long:     2 / 3
desired quantity: 1.23456789
proposal ID:      f596497b-11fd-5213-9ccb-9960a4b10ec1
reason:           Short SMA (2)=10.5 crossed above long SMA (3)=10.33333333333333333333333333.
```

Regression coverage requires this exact result under the compatible default,
low-precision `ROUND_DOWN`, and high-precision `ROUND_UP` ambient contexts. The
Architecture-94 plan, strategy proposal, canonical artifact bytes, SHA-256,
byte length, and checkpointed request must also remain identical under normal
and hostile ambient contexts.

## Frozen seed LF checkout contract

The frozen first-operation history seed is not modified. `.gitattributes`
explicitly requires an LF worktree representation:

```text
docs/validation/evidence/pd2d1-spy-strategy-history-seed-2026-08-28.json text eol=lf
```

The exact checkout contract is:

```text
byte length: 1060
SHA-256:     40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64
last newline: LF
must not end: CRLF
```

This makes the frozen byte contract portable when machine-wide
`core.autocrlf=true` without weakening the expected digest or length.

## Production protection and historical evidence

No D7-A, D7-C, publication, provisioning, provider, scheduler, credential,
broker, Paper-v2, D8-B, or live operation was performed for this candidate. All
eight committed production effect gates remain false.

The earlier accepted D7-A evidence remains historical:

```text
classification:             READY
candidate decision:          f2188b5e-e6a4-5398-be41-8867d9268355
intended execution session:  2026-09-21
```

The requalified candidate must not be assumed to reproduce that decision ID.
After exact-diff review and fresh full D7 source certification, a new separately
authorized read-only D7-A must reconstruct current production truth. D7-C
remains unauthorized.


## Replacement production D7-A read-only qualification — ACCEPTED

A fresh genuine Trading-principal D7-A qualification was run from a disposable
detached checkout pinned to the exact replacement certified source:

```text
HEAD: acd606a41ac50f172ac62377ce6d4e7c8c4d3a32
TREE: 784695d05865a767ba187adf38fd4924897127a9
```

The qualification returned exit code 0 and the following accepted evidence:

```text
classification:                    READY
completed_session:                 2026-09-18
selected_history_count:            6
required_history_count:            6
selected_snapshot_id:              680b260f-08c9-5923-87bb-b5f0a4701380
candidate_decision_id:             f2188b5e-e6a4-5398-be41-8867d9268355
intended_execution_session:        2026-09-21
regular_open:                      2026-09-21T13:30:00+00:00
account_predecessor_checkpoint_id: ed4640e5-0630-525d-b916-d50e31e3ba2a
namespace_classification:          PRESENT_VALID
storage_classification:            ABSENT
deadline_open:                     true
all_eight_gates_closed:            true
real_effect_performed:             false
```

The candidate decision ID exactly matches the earlier historical D7-A candidate,
proving the Decimal determinism correction preserved the real production
decision identity for this cycle. The repository-owned LF checkout contract
also allowed qualification from the certified source without the earlier
checkout-level `core.autocrlf=false` workaround.

D7-B remains unnecessary because the namespace is `PRESENT_VALID`.
D7-C remains the next protected production effect and is explicitly
unauthorized until separate operator approval.


## First approved D7-C attempt — BLOCKED / EFFECTS-CLOSED

An explicitly approved first D7-C publication attempt was preceded immediately
by a fresh D7-A preflight from the exact replacement-certified source. The
preflight passed with the accepted READY candidate
`f2188b5e-e6a4-5398-be41-8867d9268355`.

The single D7-C invocation then returned:

```text
classification:             BLOCKED
decision_id:                null
selected_session:           null
intended_execution_session: null
real_effect_performed:      false
exit code:                  6
```

No retry was attempted and D7-D was not run because no durable publication was
reported. The null decision/session fields together with
`real_effect_performed=false` place the failure before the publication writer
or real effect boundary.

Source review identified a process-local P2 reader-lifetime defect in the older
production history composition: `build_personal_desktop_unattended_c3_history`
creates the history reader locally, returns selected-C3 permits whose provenance
is weakly tied to that reader, and then
`create_personal_desktop_unattended_paper_decision_intent` revalidates those
permits after the reader can leave scope. D7-A does not exhibit the defect
because its production dependencies deliberately retain the relevant readers.

The required correction is to preserve the reader/provenance lifetime through
decision-intent construction without weakening permit validation. Because the
shared helper is also used outside D7-C, this must be fixed at the shared
composition boundary rather than bypassed only in the publication launcher.

No second D7-C attempt is authorized by this record. A source correction,
focused regression, full replacement certification, and fresh read-only D7-A
qualification are required before another publication approval decision.


## Selected-C3 reader/provenance lifetime source correction — PENDING REVIEW

The shared selected-C3 history composition has been corrected on the isolated
source branch `feature/pd4-d7c-reader-lifetime-fix`, based exactly on the
effects-closed failure-record commit:

```text
base HEAD: bbdc3c3073bdf3c7fe264ec4b9bd5af780dc5c8c
base TREE: 9b77611533a0944a77c08d5e4d2d8f041721949d
```

The pre-fix regression reproduced the production failure shape: the shared
history builder validated all selected-C3 permits while its local P2 reader was
alive, returned, and then exposed dead weak-reference provenance at downstream
history-binding revalidation.

The correction adds a bounded, opaque, non-copyable, non-serializable P2
provenance-lifetime object. The production history factory attaches that object
to a private `init=False`, `repr=False`, `compare=False` field on the
process-local `SelectedC3StrategyHistoryBinding`. It strongly retains only the
exact P2 readers already proven to have issued the six permits in that binding.
The existing P2 registries remain weak, no global strong registry was added,
and the ordinary disposable/history binding constructor remains available
without retained production provenance.

Neither `require_selected_c3_snapshot_matches_authority` nor
`require_selected_c3_strategy_history_binding` was weakened. Both still
revalidate the exact permits, audits, readers, cores, registrations, and C1
identity. Real disposable-P2 lifetime coverage proves that the permit remains
valid only while the proof-owned lifetime is live and fails normally after that
lifetime is released and garbage collection removes the issuing reader.

The shared daily-cycle path now consumes the retained history successfully, and
the D7-C source test reaches decision construction through the real shared
history composition boundary rather than a non-expiring `SimpleNamespace`
history reader. The private field is excluded from equality and representation,
and the decision serializer/identity material is unchanged; the deterministic
D7 fixture remains byte-identical across independent wake reconstruction.

No D7-A, D7-C, D7-D, D8, scheduler, provider, credential, Paper-v2 mutation,
broker, or live operation was performed. All eight committed effect gates
remain false. The historical production candidate remains:

```text
f2188b5e-e6a4-5398-be41-8867d9268355
```

Exact reproduction of that real-host candidate remains a required fresh
read-only D7-A gate after exact-diff review and full replacement source
certification. This source-fix checkpoint does not authorize another D7-C
attempt.


## Selected-C3 reader-lifetime replacement source certification — ACCEPTED

The reader/provenance lifetime correction is accepted and fully certified at:

```text
HEAD: 8bc6d436142531dec17bf7b960a7ac1eb2e45b09
TREE: 18255e5272728a5bf2b8f8633fff23cf940b77be
```

Certification evidence:

```text
broad suite excluding Architecture-77: 5538 passed, 17 skipped
Architecture-77 clean-harness suite:    775 passed
combined:                               6313 passed, 17 skipped
Ruff check:                             PASS
Ruff format --check:                    PASS (533 files)
git diff --check:                       PASS
git diff --cached --check:              PASS
worktree/index:                         clean
origin HEAD:                            exact source HEAD
```

Both Architecture-77 test modules were byte-identical between the candidate and
the clean integration harness. Import proof resolved the exercised
`trading_bot`, selected-C3 P2, and selected-C3 history modules beneath this
candidate source tree. No ACL or permission workaround was used.

The frozen strategy-history seed remains:

```text
byte length: 1060
sha256: 40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64
```

This supersedes the earlier replacement-certified source for purposes of the
next D7-A qualification. The failed D7-C attempt remains accepted fail-closed
evidence and does not authorize a retry.

Next checkpoint: fresh zero-argument read-only D7-A pinned to this exact source.
D7-C remains unauthorized pending a new explicit approval after that
qualification succeeds.


## Post-reader-lifetime-fix production D7-A qualification — ACCEPTED

Fresh zero-argument read-only D7-A was run from a disposable checkout pinned to
the exact reader-lifetime replacement-certified source:

```text
HEAD: 8bc6d436142531dec17bf7b960a7ac1eb2e45b09
TREE: 18255e5272728a5bf2b8f8633fff23cf940b77be
```

The qualification returned exit code 0 with:

```text
classification:                    READY
completed_session:                 2026-09-18
selected_history_count:            6
required_history_count:            6
selected_snapshot_id:              680b260f-08c9-5923-87bb-b5f0a4701380
candidate_decision_id:             f2188b5e-e6a4-5398-be41-8867d9268355
intended_execution_session:        2026-09-21
regular_open:                      2026-09-21T13:30:00+00:00
account_predecessor_checkpoint_id: ed4640e5-0630-525d-b916-d50e31e3ba2a
namespace_classification:          PRESENT_VALID
storage_classification:            ABSENT
deadline_open:                     true
all_eight_gates_closed:            true
real_effect_performed:             false
exit code:                         0
```

This reproduces the same accepted candidate after both the Decimal correction
and selected-C3 reader-lifetime correction. The production state remains
eligible for publication, but no publication effect was performed.

The first D7-C approval remains consumed by the earlier effects-closed BLOCKED
attempt. A second D7-C invocation requires a new explicit operator approval and
a fresh immediate preflight.


## Second approved D7-C publication — PROCESS SUCCESS; D7-D EARLY BLOCKED

After fresh post-fix D7-A preflight passed from certified source
`8bc6d436142531dec17bf7b960a7ac1eb2e45b09`, one newly approved D7-C
invocation returned:

```text
classification:             DECISION_PUBLISHED
decision_id:                f2188b5e-e6a4-5398-be41-8867d9268355
selected_session:           2026-09-18
intended_execution_session: 2026-09-21
real_effect_performed:      true
exit code:                  0
```

No second publication invocation was made.

The immediately following independent D7-D read-only reconciliation returned:

```text
classification:                    BLOCKED
completed_session:                 null
expected_decision_id:              null
finalized_decision_id:             null
selected_history_count:            0
namespace_classification:          null
storage_classification:            null
all_eight_gates_closed:            false
real_effect_performed:             false
exit code:                         6
```

Because D7-D retained only its default evidence object, the reconciliation
failed before its first evidence commit (which occurs only after completed
session, selected-C3 history, and namespace qualification). This does not by
itself contradict the D7-C process result, but D8 must not proceed until durable
publication state is independently proven and the D7-D early-block cause is
understood.

Next safe step: rerun zero-argument D7-A read-only from the same exact certified
source. If it reports ALREADY_FINALIZED / FINALIZED_IDENTICAL for the accepted
candidate, treat that as independent durable publication evidence while
continuing D7-D diagnosis. No republish or D8 action is authorized.


## Durable post-publication proof and D7-D admission root cause

A fresh zero-argument D7-A read-only qualification after the successful D7-C
publication returned:

```text
classification:                    ALREADY_FINALIZED
candidate_decision_id:             f2188b5e-e6a4-5398-be41-8867d9268355
storage_classification:            FINALIZED_IDENTICAL
completed_session:                 2026-09-18
selected_history_count:            6
required_history_count:            6
selected_snapshot_id:              680b260f-08c9-5923-87bb-b5f0a4701380
intended_execution_session:        2026-09-21
account_predecessor_checkpoint_id: ed4640e5-0630-525d-b916-d50e31e3ba2a
namespace_classification:          PRESENT_VALID
deadline_open:                     true
all_eight_gates_closed:            true
real_effect_performed:             false
```

The D7-A CLI maps `ALREADY_FINALIZED` to exit code 0. This independently
proves the published D7 decision is durably present and byte/identity exact.
No republish is permitted.

Source review then identified the D7-D early-block root cause. Production
`read_personal_desktop_paper_account()` returns a
`ValidatedPersonalDesktopPaperAccount` process-local capability, while
`require_validated_personal_desktop_paper_account()` returns immutable read
evidence. D7-D currently overwrites the pre-lock capability with that evidence
and passes the evidence to `supervised_paper_cycle_admission()`. The admission
boundary explicitly requires the genuine validated capability, so D7-D fails
at mutex admission before its first diagnostic evidence commit. D7-A correctly
retains the original pre-lock capability for admission and uses the required
evidence only for comparison.

Required correction: retain the pre-lock account capability separately, derive
evidence from it for identity/predecessor comparison, and pass the original
capability into admission. Do not weaken account provenance or mutex admission.
D8 remains blocked until corrected D7-D independently reconciles the finalized
decision.
