# Architecture 134-F1R1-D1: Fresh Successor Soak Design

Status: DESIGN FROZEN; docs-only checkpoint. This document defines a future
source and production-effect boundary. It does not implement the successor,
install a release, create a scheduler task, read credentials, contact a
provider, mutate paper state, place an order, or authorize any soak.

## Checkpoint and evidence boundary

This design starts from the exact accepted C1/C2 integration state:

```text
develop HEAD  1490f0391a49150dee913ca029cd2838774d5343
develop TREE  fc02c35af88419a3e2b8c2dffd8fc5e19ad71850
C1 source gate 39732123326 / attempt 1 / SUCCESS
post-merge develop gate 39736130846 / attempt 1 / SUCCESS
```

The C2 qualification result is terminal PASS:

```text
RUNTIME_ID qualification-573ce39f76eb8a4b5e789f1e2d4d97828bff0269274ebce64147192eb8ef83cf
interpreter C:\Program Files\Python314\python.exe
Python 3.14.3
interpreter SHA256 cce21c0e8710e30427398ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b
PID 31084
birth windows-filetime:134371269159496809
```

Its exact classification was:

```text
RUNTIME_ID_UNCHANGED=YES
SURVIVED_DEVELOPMENT_ACTIVITY=YES
SURVIVED_CODEX_RESTART=YES
DUPLICATE_HOST=NO
LIFECYCLE_REPLAY_VALID=YES
TERMINAL_NORMAL_RETURN=YES
PROTECTED_EFFECTS=ZERO
F1R1_EXTERNAL_HOST_QUALIFICATION=PASS
```

C2 proves an independent harmless process lifetime, exact process identity,
one process-lifetime lease, development/Codex-restart survival, canonical
terminal replay, and zero protected effects. It is not Architecture-133
InstalledEvidence, RuntimeAdmissionEvidence, Architecture133HostBinding,
successor-soak authority, scheduler authority, provider or credential
authority, paper or broker authority, D1/D2 authority, or live authority.

The fixed C2 evidence root is consumed evidence:

```text
F:\AI\temp\qualification\arch134-f1r1-host-isolation
```

It must never be deleted, reset, re-prepared, relaunched, repaired,
truncated, rewritten, or treated as reusable authority. A future milestone may
reference it only read-only and only under a separately reviewed boundary.

The original Architecture 134-F parent/child lineage remains permanently
`FINAL / INDETERMINATE / CONSUMED`. Its parent series identity, durable
authority slot, child identities, scheduler task identity, worktree, launcher,
D1R7/D1R8 operations, and retry/resume authority are not inputs to this design.

## Fresh successor lineage

D1 creates a new, versioned semantic family. The following names are frozen
for the future source implementation:

```text
design schema       arch134-f1r1-d1-successor-soak-design/v1
lineage schema      arch134-f1r1-d1-successor-lineage/v1
evidence schema     arch134-f1r1-d1-successor-evidence/v1
identity namespace  arch134-f1r1-d1-successor-soak-identity/v1
evidence root      F:\AITradingBot\Arch133\arch134-f1r1-d1-successor-soak-v1
parent file         successor-parent-v1.jsonl
session files       successor-session-01-v1.jsonl
                    successor-session-02-v1.jsonl
```

The evidence root is a future production durable namespace beneath the
accepted durable-data parent, not the C2 qualification root and not the old F1
parent slot. D1 does not create or inspect it. The source checkpoint must
admit the exact root as a new successor store and reject aliases, reparse
points, alternate parents, existing foreign state, and any old F1/C2 path.

The future parent identity is UUID5 over canonical, versioned semantic
material in the new D1 namespace. It must include the exact accepted successor
source/release identity, Architecture-133 production binding/admission
identity, F1R1 installed-runtime and host-composition identity, production
runtime ID, strategy and risk identities, fixed product scope, ordered session
tuple, and every effect ceiling. It must exclude clocks, PIDs, random values,
filesystem paths, Git worktree state, serialized journal bytes, and scheduler
runtime state. The future child/session identity is a separate UUID5 over the
parent identity, ordinal, fixed target session, and versioned session contract.
No old F1 UUID namespace, parent identity, child identity, or evidence digest
may appear as authority material.

Historical F1/C2 facts may be recorded in a non-authorizing predecessor note,
but they cannot be used to derive, resume, or extend the successor parent.

## Production admission is independent

The successor may run only from an already-installed immutable production
release. The future admission chain must independently prove, in this order:

1. The exact accepted successor source HEAD/TREE and release manifest are
   bound to one immutable release ID and complete source inventory.
2. The release is installed at the exact Architecture-133 production release
   root `F:\AITradingBot\releases\<release-id>`; no checkout or worktree is
   an executable source.
3. The Architecture-133 `RuntimeBinding`, installed-image evidence,
   `RuntimeAdmissionEvidence`/`RuntimeAdmissionResult`, and
   `Architecture133HostBinding` agree on release, manifest, binding, source,
   launcher, Python, image, dependency, and inventory identities.
4. F1R1-A immutable runtime admission and F1R1-B production host composition
   and readiness are freshly revalidated against that installed release and
   the new durable store. Replaying a cached result is insufficient.
5. The runtime process uses the accepted production substrate:

   ```text
   executable       F:\AITradingBot\runtime\python.exe
   startup          -I -S -B <FINAL>\scripts\run_arch133_supervised_release_review_paper.py
   source root      <FINAL>\src
   working dir     <FINAL>
   no-pycache       F:\AITradingBot\Arch133\no-pycache
   site packages    F:\AITradingBot\runtime\Lib\site-packages
   semantic args    none
   ```

   Exact version/hash, import origins, no-site/no-bytecode facts, substrate
   security, and before/after stability remain mandatory.
6. Only after those read-only checks pass may a separately reviewed effect
   preflight consider the successor.

After admission, Git, GitHub, remote refs, branch status, checkout paths, and
development activity are irrelevant. The successor must reject execution from
`F:\AI\ai-trading-bot`, any `F:\AI\worktrees\...` path, the C2 fixture, or any
mutable checkout. C2 qualification evidence cannot satisfy any item above.

The current D1 base commit is design provenance only. The future installed
release identity is fixed by the later source-implementation checkpoint and
must not be guessed from this design branch.

## Operational objective and fixed sessions

The successor validates the production runtime, provider, and synthetic
review-paper operational path after the F1R1 host-isolation correction. It is
not a profitability, strategy-quality, promotion, or research-eligibility
gate. Architecture 145 remains the separate offline owner of historical
robustness, walk-forward and out-of-sample evidence, parameter and regime
stability, conservative execution stress, sealed holdout, and inert later
`LIVE_CANARY_ELIGIBLE` evidence.

### Two-session decision

D1 freezes exactly **two** published regular NYSE sessions. One session is not
enough to distinguish first-entry behavior from durable progression or a fresh
manual admission. Two sessions are the smallest finite window that can prove:

- one complete operational session;
- one subsequent session using the same durable successor parent;
- one fresh explicit manual-start admission for the second session; and
- bounded progression after a benign, risk-rejected, or expected paper result.

A third or fifth session would add exposure without establishing a new
authority or reboot property. The design therefore does not inherit F1's five
sessions merely because F1 used five.

The source checkpoint must encode this exact finite tuple as two literal dates
from the accepted NYSE published-session manifest. For this D1 design the
reserved tuple is:

```text
ordinal 1: 2026-11-02
ordinal 2: 2026-11-03
```

They are ordinary regular sessions in the current frozen 2026-2028 session
manifest. The dates are source-owned semantic material, not a runtime date
selection instruction. If the source, production admission, or effect
preflight is not accepted before the tuple is missed, the tuple is simply
missed and the successor cannot catch up, replace, backfill, or dynamically
extend it. A later date requires a new reviewed design/source identity.

The product scope is fixed to `SPY`, long-only US ETF review-paper behavior,
with no caller-selected symbol, account, provider, quantity, strategy, risk
policy, date, or evidence path. Strategy and risk identities are the exact
source-owned projections of the admitted release manifest; the caller cannot
replace them at start time.

## Lifecycle and reboot contract

Task Scheduler is explicitly excluded. A two-session manual-start model is the
smallest production-representative surface for this short successor. D1 has no
task name, trigger, action, restart policy, demand-start authority, or scheduler
evidence. No scheduler read, create, update, delete, run, rebind, or retirement
operation is part of the successor.

The frozen lifecycle is:

```text
RUNNING
  -> intentional shutdown/reboot/logoff terminates process
  -> STOPPED after boot/login
  -> optional read-only reconciliation
  -> explicit operator start
  -> fresh release/runtime/host/authority admission
  -> RUNNING
```

No boot or logon trigger may enter a provider or paper loop. The future source
must not copy F1's `--resume` or logon-auto-resume behavior. The first session
is entered by one explicit manual start. The second session is entered by a
second explicit manual start against the same durable, already-authorized
successor parent after the first session is terminal. If a reboot or logoff is
used between sessions, it is a separate reviewed operator action; after login,
the process remains stopped until that manual start.

The second start may continue only the exact durable parent and next fixed
ordinal. It must not manufacture a new parent or child, replace a missed
session, retry an ambiguous intent, or treat a process restart as fresh
authority. If the durable series is final, a later start is read-only and
returns the existing terminal result.

## Effect entry, retry, and ambiguity

Every future externally effectful seam follows the F1R1-A entry model:

1. Fresh source/runtime/host admission and durable successor evidence are
   complete before the seam is considered.
2. A canonical `INTENT` and then `ENTRY_ADMITTED` record is durably appended
   before the external seam is called.
3. A rejection proven before seam entry appends `PRE_ENTRY_REJECTED` and closes
   the session as `BLOCKED`; it proves no external entry.
4. Once entry may have occurred, a missing or conflicting result is
   `AMBIGUOUS`/`INDETERMINATE`. That session and parent authority are consumed,
   and the entire series halts.
5. A successful result is not acknowledged until the canonical `ACK` and
   required read-back are durable.

There is no automatic retry, provider reacquisition, second paper attempt,
timeout-based authority, stale-lock takeover, lock deletion, repair,
truncation, journal rewrite, or ambiguous-state recovery by mutation.
Read-only reconciliation is the only response to an ambiguous external
entry. A pre-entry rejection is also consumed as a session attempt; the
successor does not retry that session through a different path.

## Successor evidence contract

The future source must implement one canonical append-only JSONL contract under
the new evidence root. The header binds:

- `arch134-f1r1-d1-successor-evidence/v1`;
- the exact accepted successor source HEAD/TREE, release ID, manifest digest,
  launcher digest, inventory digest, and release-relative source identity;
- exact Architecture-133 production binding/admission identity and installed
  image identity;
- F1R1 installed-runtime and host-composition/readiness identity;
- the production runtime ID, not the C2 qualification runtime ID;
- exact strategy ID/version/config digest and risk-policy ID/version/digest;
- fixed `SPY` product scope and long-only review-paper mode;
- the ordered two-date session tuple;
- every frozen effect ceiling;
- the fresh parent/lineage identity and child/session identities; and
- the evidence schema/version and predecessor note as non-authorizing history.

Observed clocks, OS process IDs, process birth identity, file identity, and
provider response metadata may appear as evidence where required, but they are
not deterministic domain identity material. Secrets, credentials, tokens,
provider bodies, arbitrary exception text, stack traces, Git paths, and mutable
environment text are excluded or reduced to closed classifications.

The append-only event set must include, at minimum:

```text
PARENT_RESERVED
SOURCE_ADMITTED
RUNTIME_HOST_ADMITTED
SESSION_TUPLE_BOUND
SESSION_01_GRANT_INTENT
SESSION_01_FINAL
SESSION_02_GRANT_INTENT
SESSION_02_FINAL
SERIES_COMPLETED or SERIES_HALTED
```

Each session record binds its exact child ID, ordinal, target date, grant
prefix, per-seam intent/entry/ack or pre-entry rejection, terminal
classification, observed process evidence, and protected-effect counters.
The parent terminal record binds the final pre-terminal journal prefix,
ordered session digests, terminal classifications, and complete counters.
Replay must validate exact sequence numbers, canonical bytes, one runtime ID,
append-only ordering, bounded size, no duplicate child, and no terminal
extension. A malformed, partial, mismatched, over-budget, or consumed journal
fails closed without repair.

## Session terminals and progression

The successor terminal set is deliberately small and explicit:

| Session terminal | External entry | Parent progression |
| --- | --- | --- |
| `NO_SIGNAL` | provider entry acknowledged; no paper mutation | session closes; next fixed date allowed |
| `RISK_REJECTED` | provider entry acknowledged; risk rejected | session closes; next fixed date allowed; nonqualifying |
| `PAPER_EXECUTED` | provider and paper mutation acknowledged | session closes; next fixed date allowed |
| `SESSION_MISSED` | no effect entry | session closes; parent halts |
| `BLOCKED` | pre-entry rejection proven | session closes; parent halts |
| `INDETERMINATE` | entry may have occurred; outcome ambiguous | consumed; parent halts |

`NO_SIGNAL`, `RISK_REJECTED`, and `PAPER_EXECUTED` are the only terminals
that allow progression to the next fixed tuple member. `RISK_REJECTED` is an
operational result, not a quality or profitability pass. `SESSION_MISSED`,
`BLOCKED`, and `INDETERMINATE` halt the complete series. An ambiguous external
entry always remains consumed even when later read-only reconciliation can
describe what happened; reconciliation cannot reopen the session or grant a
new attempt.

The final two-session parent result is operationally complete only when both
children are closed, independently replayed, and their counters and digests
match the parent. It does not grant Architecture 145 eligibility, D2,
promotion, or live authority.

## Frozen effect ceilings

These are successor-specific ceilings, not copied F1 counters:

| Effect | Ceiling for one successor parent |
| --- | ---: |
| successor parent/authority creation | 1 |
| child/session grants | 2 total; 1 per fixed date |
| fresh manual-start process admissions | 2 total; 1 per fixed date |
| fresh successor prerequisite grants/admissions | 2 total; 1 per fixed date |
| fresh successor prerequisite proof/publication operations | 2 total; 1 per fixed date |
| historical D1R7/D1R8 operations or evidence reuse | 0 |
| market-data/provider entry attempts | 2 total; 1 per fixed date |
| provider reacquisition/retry | 0 |
| synthetic review-paper session attempts | 2 total; 1 per fixed date |
| synthetic paper mutations/fills | 2 total; 1 per fixed date |
| broker-paper operations | 0 |
| credential reads for the successor operation | 2 total; one bounded read phase per date |
| production release installation/publication | 0 during the soak |
| scheduler/task reads, creates, updates, runs, deletes, or rebinds | 0 |
| automatic startup/logon resumes | 0 |
| intentional reboot/logoff transitions required by the soak | 0; never induced by the runtime |
| read-only post-reboot reconciliations | 2 maximum; no mutation |
| broker order placements/cancels/replaces | 0 |
| D2 operations | 0 |
| promotion or strategy changes | 0 |
| live-money effects | 0 |

The source implementation must expose these counters in canonical evidence and
reject any nonzero or over-ceiling value. It must not add hidden provider,
credential, paper, scheduler, broker, or process attempts beneath a generic
retry helper. If the current production topology no longer needs the
successor-prerequisite phase, its source-owned ceiling must be explicitly set
to zero in a separately reviewed source contract; it cannot be silently
removed or inherited from F1.

## Source/effect gate separation

The only permitted future sequence is:

```text
D1 design acceptance
  -> source implementation checkpoint
  -> focused verification
  -> one atomic publication
  -> mapped terminal CI
  -> ChatGPT exact-source acceptance
  -> separate production installed-release/readiness admission
  -> separate effect preflight
  -> separately bounded successor-soak execution
```

No design, source, focused test, CI, or ChatGPT source acceptance grants
installation, scheduler, credential, provider, paper, broker, D1/D2, promotion,
or live authority. The D1 source checkpoint must not register a new executable
checkpoint in `checkpoint_runner.py` merely for this design document.

## Non-goals and stop conditions

Real-money trading remains NO-GO. This design adds no live broker placement,
live credentials, live position mutation, live order/cancel/replace, margin,
leverage, short selling, options, or crypto.

Stop and return for review if implementation would require changing accepted
Architecture-133/F1R1-A/B source, mutating or reusing C2/F1 evidence, using a
mutable checkout, retaining automatic reboot resume, adding a scheduler,
reusing an old authority identity, retrying an ambiguous entry, or making any
provider/paper/broker/live effect during the design or source checkpoint.

Also remove or update any tests and docs that referenced the old behavior.

## Next milestone

The next milestone is a source-only implementation of this exact D1 contract.
The recommended owner is Sol High because the implementation changes runtime,
ordering, authority, and external-effect containment. That source checkpoint
must add the fresh successor namespace and evidence codec, preserve accepted
F1R1-A/B and Architecture-133 source bytes, implement the two-session manual
start lifecycle and terminal matrix, run focused tests plus cheap source checks,
publish one atomic commit, and wait for the mapped terminal source gate.

Only after ChatGPT accepts that exact source may a separately reviewed
installed-release/readiness admission and effect preflight be prepared. No
successor-soak execution is authorized by D1.
