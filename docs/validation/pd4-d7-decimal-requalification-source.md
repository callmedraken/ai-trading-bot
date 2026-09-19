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
