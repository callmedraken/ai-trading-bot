# PD4 Unattended Daily Cycle Validation and Deployment Plan

Status: PD4-G0 planning checkpoint; documentation only; every real effect remains closed.

Architecture:

```text
docs/architecture/111-personal-desktop-unattended-daily-cycle-authority.md
```

This plan turns Architecture 111 into bounded source checkpoints and then into separately authorized real-host deployment/effect checkpoints. It does not itself authorize provider call #7, Task Scheduler mutation, production storage provisioning, decision publication, Paper-v2 execution, receipt recovery, broker-paper, or live trading.

## 1. Baseline and invariant source state

The accepted PD4 source baseline before this Architecture-111 work is:

```text
certified source commit: 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
certified source tree:   5e867f1bfc6d945ad67f6c56be252b534645aeb2
full suite:              5588 passed, 17 skipped
```

Docs-only PD4 closeout commits after that certification are not source changes.

The source-development branch remains:

```text
feature/personal-desktop-paper-runtime
```

All source checkpoints must begin from a clean explicitly named worktree and preserve unrelated generated/untracked artifacts.

Existing six Paper-v2 gates begin and remain false during G1–G7 source development:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED = False
```

Architecture 111 adds two more closed-by-default source gates:

```text
PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = False
```

Source implementation and tests must not flip any production gate to `True`.

## 2. Validation philosophy

Each source checkpoint is accepted only after:

```text
exact changed-file review
focused pytest for affected contracts
focused Ruff check
focused Ruff format --check
git diff --check
git diff --cached --check
clean worktree/index at checkpoint boundary
```

Do not run the complete repository suite after every intermediate G checkpoint.

Run one full repository certification only after G6 exact source acceptance on the final unchanged source tree as G7, unless a subsequent meaningful source correction requires a replacement final certification.

Docs-only closeout after successful G7 does not require another full suite.

## 3. PD4-G1 — Pure XNYS timing/session/deadline policy

### Goal

Implement Architecture 111 timing semantics without I/O or effects.

### Required source behavior

Introduce a narrow public policy for:

```text
regular_open(session)
derive intended execution session from selected completed session
pre-open eligibility classification
missed-deadline classification
```

Version 1 regular open:

```text
09:30:00 America/New_York on the modeled XNYS session date
```

The policy must use the existing XNYS descriptor/calendar ordering and must not modify the `MarketCalendar` protocol.

### Required tests

Cover at least:

- normal Eastern Standard Time session;
- normal Eastern Daylight Time session;
- DST transitions without fixed-offset assumptions;
- weekends;
- modeled exchange holidays;
- early-close sessions retaining 09:30 regular open;
- `now < open`, `now == open`, and `now > open` boundaries;
- next-session derivation across Friday/weekend;
- next-session derivation across modeled holidays;
- invalid/unmodeled date rejection;
- deterministic/pure behavior independent of system local timezone.

### Model routing

Localized/frozen contract after G0: Luna Extra High is appropriate.

## 4. PD4-G2 — Session-indexed selected-C3 read and history binding

### Goal

Allow the zero-argument unattended runtime to obtain exact selected C3 evidence for a required session and derive authoritative rolling strategy history without caller selection IDs or filesystem discovery.

### Required source behavior

Add a production read boundary that:

1. derives canonical unattended C3 request material for exact session `S` and source-owned profile;
2. queries production authority read-only for exactly one matching `SUCCESS_SELECTED` lineage;
3. rejects zero/multiple candidates;
4. passes the resolved exact selection through the established strict P2 artifact verification path;
5. binds the result to the current C1 authority.

Add `SelectedC3StrategyHistoryBinding` or equivalent public authority evidence that:

- retains ordered exact selected-C3 session/artifact evidence;
- constructs/reconciles canonical `StrategyHistorySeed` bytes as a pure inner data structure;
- keeps the existing seed source descriptor non-authoritative;
- proves every required history bar came from the selected-C3 chain;
- requires the configured consecutive-session suffix;
- rejects duplicates, gaps, stale sessions, wrong symbols, wrong authority, wrong artifacts, and noncanonical seed bytes.

### Required negative tests

At minimum:

- wrong C1 authority;
- wrong request bytes for the same apparent session;
- no selected lineage;
- duplicate matching selected lineage;
- selected artifact digest mismatch;
- file-identity mismatch;
- nonconsecutive strategy history;
- history containing current/future session;
- wrong symbol;
- offline seed substitution attempt;
- any database mutation during read;
- filesystem directory order/newest-file cannot affect selection.

### Model routing

Cross-module discovery/read-authority integration: Astra for bounded implementation is reasonable. ChatGPT retains architecture and exact diff acceptance.

## 5. PD4-G3 — Two-phase Architecture-94 decision construction

### Goal

Split pre-open decision formation from later open-reference completion while preserving the existing final plan contract exactly.

### Required source behavior

Expose a public pure pre-open decision representation and builder conceptually equivalent to:

```text
build_manual_paper_strategy_decision(...)
complete_manual_paper_strategy_plan(...)
```

The pre-open decision must retain enough canonical semantic evidence to replay:

- exact selected current snapshot;
- exact C3 history binding / canonical history seed;
- prior account/checkpoint evidence;
- strategy config;
- strategy evaluation/result;
- target and planner-relevant decision evidence;
- intended execution session;
- policies;
- deterministic caller-idempotency material;
- modeled submitted/filled regular-open instant.

It must contain no execution-session open price.

The completion function must require an exact verified execution-session open binding and emit the existing `ManualPaperStrategyPlanArtifactBinding`.

### Golden compatibility gate

For existing legacy test vectors, assert exact equality of:

```text
final plan model
serialized final plan bytes
plan ID
artifact SHA-256
artifact byte length
checkpointed request
request ID
target
planner identities
operation/application downstream identities where established fixtures expose them
```

between old one-phase construction and the new two-phase path.

The old public one-phase builder may remain as a compatibility wrapper.

### Required anti-lookahead tests

Prove the pre-open decision:

- cannot accept an open-reference argument;
- cannot derive/read future daily-bar open;
- has stable identity if later execution open changes;
- produces different final plan identity only at the later completion boundary when the open binding differs;
- cannot complete with a selected C3 session different from intended execution session.

### Model routing

After the exact G0/G2 contracts are known, much of this is localized deterministic refactoring: Luna Extra High is preferred unless repository discovery exposes cross-module complications.

## 6. PD4-G4 — Durable decision intent and pre-open publication authority

### Goal

Create durable proof that the strategy decision existed before its intended execution open, while keeping production publication closed.

### Required source behavior

Freeze and implement:

- canonical decision-intent schema/serializer/parser/verifier;
- deterministic UUID5 decision identity;
- fixed production decision namespace constant;
- strict read-only decision-storage classification;
- hardened one-shot decision output capability;
- process-local `PreOpenDecisionPublicationPermit` or equivalent;
- new decision-publication gate default `False`;
- pure/read-only qualification path that proves the production effect remains closed.

### Publication invariants

The production capability must require:

```text
current C1 authority
exact decision identity
exact intended execution session
observed current time strictly before regular open
expected exact gate combination
fixed production namespace/security profile
```

The permit cannot be copied, serialized, pickled, reconstructed from decision bytes, or reused.

### Storage negative tests

Cover:

- absent namespace;
- wrong owner/ACL;
- reparse/symlink parent;
- staging exists;
- conflicting final bytes;
- identical final bytes;
- parent identity drift;
- failed flush/finalization/readback;
- late publication at or after open;
- duplicate permit use;
- capability attempts to write outside decision namespace.

### Model routing

Production Windows/storage/security authority: Sol High.

## 7. PD4-G5 — Zero-argument unattended C3 composition

### Goal

Allow an effects-closed zero-argument production composition to derive the exact C3 request for the completed session and prove at-most-once convergence before any real provider authorization.

### Required source behavior

The source-owned unattended profile derives:

```text
S = exact eligible completed XNYS session
request_window_start_date = S
request_window_end_date = S
target_session_date = next_session(S)
ordered_universe = source-owned profile universe
```

The production path may reach the existing `WindowsEffectfulDailySnapshotCapture` only when the new market-data effect gate is open under a reviewed exact gate combination.

During G5 source development the gate remains `False`; production tests must prove no credential access, child creation, HTTP/provider request, SQLite mutation, or output publication occurs.

Disposable seams must prove:

- duplicate wakeups converge on the same session request;
- an existing selected snapshot returns read-only convergence rather than a provider call;
- ambiguous/consumed C3 prior state never retries blindly;
- stale/late wall clock cannot nominate a different session;
- session gaps classify and stop;
- provider call budget remains exactly the existing C3 one-shot semantics.

### Model routing

External-effect containment and C3 authority: Sol High.

## 8. PD4-G6 — Complete unattended daily-cycle controller

### Goal

Compose all accepted pieces into one zero-semantic-argument daily state machine while every real effect remains closed in production source.

### Required ordering

The controller must implement the Architecture-111 ordering:

```text
validate C1
-> reconcile completed/selected C3 session
-> reconcile any finalized pending decision targeting that session
-> if settlement evidence is ready, reconstruct exact final plan
-> enter existing PD4/A67 startup reconciliation
-> classify execution state without fresh effect while gate closed
-> strict Paper-v2 account reread
-> build exact C3-backed strategy history through selected session
-> construct next pre-open decision
-> classify decision publication eligibility without publication while gate closed
-> emit bounded sanitized result
```

No mutex may be held across C3 provider effects. Existing PD2A/A67 lock and recovery ordering must remain unchanged.

### Required classifications

Exercise at least:

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

### Required fault matrix

Cover process restart/crash boundaries around:

- before/after selected-C3 read;
- before/after decision qualification;
- finalized decision already present;
- before/after plan reconstruction;
- A67 pending/already-applied/missing-receipt/conflicting states;
- account predecessor changed;
- current clock crosses open deadline during qualification;
- duplicate concurrent launcher processes;
- late `StartWhenAvailable` wake;
- provider unavailable/ambiguous prior state;
- history gap.

No test should require a real provider/broker effect.

### Model routing

Cross-authority composition, ordering, crash/recovery, external-effect boundaries: Sol High.

## 9. PD4-G7 — Final source certification

G7 begins only after exact G6 source review is accepted and the source tree is otherwise final.

### Focused pre-certification gates

Run the complete affected Architecture-111 test surface plus the existing PD4/PD3/C3 regression interfaces most directly touched by the changes.

Then run focused Ruff and diff checks.

### Broad certification

On the exact final unchanged source tree:

```powershell
$Python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
$Ruff = 'F:\AI\ai-trading-bot\.venv\Scripts\ruff.exe'
$BaseTemp = "F:\AI\temp\pytest\pd4-g7-final-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null

& $Python -m pytest --basetemp="$BaseTemp" -p no:cacheprovider
& $Ruff check .
& $Ruff format --check .
git diff --check
git diff --cached --check
git status --short
```

Record exact commit and tree before and after certification and require local/origin equality.

### Genuine Trading-principal read-only qualification

Using the fixed production interpreter under non-admin/non-elevated `DESKTOP-I4DOKM7\Trading`, run the final zero-argument launcher/read-only validation while all eight effect gates are false.

Acceptance requires proof of no:

```text
provider call
credential read
child launch
C3 database mutation
decision publication
Paper-v2 invocation publication
Paper-v2 execution
receipt recovery
scheduler mutation
broker effect
live effect
```

A fail-closed `BLOCKED`/`WARMING_UP`/storage-unavailable result may be acceptable if the harness itself validates the intended closed production state.

## 10. Protected deployment D1 — Provision fixed namespaces

Only after G7 source certification and a separate operator review may the production decision/invocation namespaces be provisioned if absent.

Provisioning must use the already-reviewed dedicated storage-provisioning authority patterns and exact Trading ownership/ACLs.

After provisioning:

- close the provisioning gate again;
- verify read-only security/path identity;
- perform no provider/decision/Paper-v2 execution effect in the same authorization unless explicitly included by a later checkpoint.

## 11. Protected deployment D2 — Install Task Scheduler entry

Install/modify exactly one reviewed zero-semantic-argument scheduled task under the dedicated Trading principal.

Initial intended trigger target:

```text
04:30 America/New_York
approximately 01:30 America/Los_Angeles under ordinary matching offsets
StartWhenAvailable = true only with Architecture-111 late-wake fail-closed behavior
```

Freeze exact task name, principal SID, executable, source launcher path, working-directory behavior, environment behavior, logon/run level, trigger, retry settings, concurrent-instance policy, and wake/power settings before installation.

With all effect gates closed, run/observe the task only as separately authorized and require the same effects-closed launcher evidence as manual invocation.

## 12. Protected deployment D3/D4 — First unattended C3 acceptance capture

Provider call #7 remains a distinct effect checkpoint.

Immediately before D3:

- verify exact source commit/tree;
- verify intended Trading principal/SID/non-elevation;
- verify C1/C2/C3 authority health;
- verify all unrelated effect gates closed;
- enable only the reviewed unattended market-data gate combination;
- authorize exactly one launcher invocation.

Expected normal result is one C3-authorized selected completed-session snapshot.

Any ambiguity, nonzero exit, partial output, consumed provider attempt, unexpected terminal state, or process interruption is STOP evidence; do not rerun under the same authorization.

D4 closes the market-data gate and performs read-only C3/P2 reconciliation before anything else proceeds.

## 13. Protected deployment D5 — Capture-only warm-up

After D3/D4 acceptance, permit only the already-reviewed unattended C3 capture path on normal scheduler wakes while:

```text
decision publication = closed
Paper-v2 unattended execution = closed
receipt recovery = closed
broker/live = unavailable
```

Accumulate the required consecutive selected C3 history.

For the current long window of five, require six consecutive selected sessions before first decision publication eligibility.

Every wake should expose `WARMING_UP` until that condition is met.

A gap or ambiguous provider state stops warm-up; do not fill the gap from the old offline seed.

## 14. Protected deployment D6/D7 — First pre-open decision publication

After warm-up history is accepted:

- Paper-v2 execution remains closed;
- authorize exactly one decision-publication effect for the next eligible execution session;
- require current time strictly before that session's regular open;
- finalize exactly one canonical decision intent;
- close the publication gate immediately afterward;
- read back and strictly verify exact final bytes/identity/security;
- confirm no open-reference price exists in the decision artifact.

A missed deadline does not move the decision to the next session automatically.

## 15. Protected deployment D8/D9 — First unattended Paper-v2 settlement

After the decision's intended execution session completes and an independently selected C3 snapshot for that exact session exists:

- verify the decision artifact read-only;
- verify exact C3 open binding;
- reconstruct the exact existing Architecture-94 final plan;
- verify PD4/A67 startup classification;
- authorize exactly one unattended Paper-v2 execution under its existing dedicated gate;
- perform no receipt recovery unless separately authorized;
- close the execution gate immediately after the one acceptance invocation;
- perform strict ordinary Paper-v2/A67/receipt/lineage reconciliation.

Any ambiguous or abnormal result is STOP evidence and does not authorize rerun.

## 16. Protected deployment D10 — Bounded unattended simulated-paper soak

Only after D1–D9 are individually accepted should the project describe unattended simulated-paper operation as deployed.

The initial soak should emphasize real desktop operational behavior rather than new security layers:

- normal weekday cycles;
- weekends and exchange holidays;
- DST transitions;
- Windows reboot before wake;
- Windows update/restart;
- sleep/hibernate and late `StartWhenAvailable` launch;
- duplicate task/process starts;
- network outage;
- provider HTTP/schema failure;
- provider-attempt ambiguity;
- missed decision deadline;
- missing/invalid history session;
- conflicting decision artifact;
- Paper-v2 already-applied state;
- terminal missing receipt requiring operator review;
- account predecessor mismatch;
- disk/full/storage failure where safely testable;
- process termination at reviewed crash points in disposable/acceptance harnesses.

A concrete soak duration/number of successful cycles should be frozen before D10 begins. Do not graduate to broker-paper based only on source tests.

## 17. Completion criteria for operational PD4

PD4 unattended simulated-paper operation is operationally complete only when all are true:

```text
Architecture 111 accepted
G1–G6 source accepted
G7 final source certification accepted
production namespaces accepted
Task Scheduler deployment accepted
provider call #7 acceptance reconciled
C3-only warm-up history complete
first pre-open decision publication accepted
first unattended Paper-v2 settlement accepted
all protected effects reconciled
bounded unattended simulated-paper soak accepted
no unresolved recovery/authority ambiguity
```

At that point Architecture-111 security expansion should stop unless soak evidence exposes a concrete gap.

The next major product milestone becomes PD5 broker-paper integration.

## 18. Roadmap after PD4

The expected completion path is:

```text
PD5  broker-paper adapter + account/order/fill/reconciliation/idempotency authority
PD6  unattended broker-paper composition + long operational soak
PD7  live-readiness architecture and operator/emergency controls
PD8  tiny explicitly authorized restricted live pilot
PD9  mature live operation, scaling, monitoring, backup/restore, upgrade/rollback
PD10 polished unified desktop GUI/productization over the proven service boundaries
```

Passing one stage never automatically enables the next stage's effects.

Live trading remains NO-GO until its later explicit architecture, source, host, broker, operator, and acceptance gates are separately satisfied.
