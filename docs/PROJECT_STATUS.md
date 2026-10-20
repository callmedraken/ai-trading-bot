# AI Trading Bot - Project Status

## Current verified checkpoint

Architecture 144-A / RCL-7 is **SOURCE ACCEPTED** on the isolated feature
lineage.

```text
branch  feature/test-suite-arch144-research-paper-eligibility-current
base    c5225d8f3f584eb0eb60d62e5381f1caa3c56cb2
base tree
        bf7019b1610c29563282ccb5f19be2bcb6501849
HEAD    0c3064c7576d3c91a9039d49a514aae174253f6a
TREE    b6aa255eb6bbeeeb0bcc953a24a84e4d662807e2
parent  c5225d8f3f584eb0eb60d62e5381f1caa3c56cb2
commits above base
        1
CI      Checkpoint Source Gates #638 / 39346589645
event   push
attempt 1
result  SUCCESS
```

ChatGPT independently reviewed the exact GitHub commit, all 19 changed paths,
the new Architecture-144 module/tests, current-inventory successor pins,
certification inventory/timing changes, and exact CI route. The source remains
pure and deterministic and does not acquire or verify real operational evidence.

144-A implemented:

- `ResearchStrategyPaperSessionObservation`;
- `ResearchStrategyPaperSoakPolicy`;
- `ResearchStrategyPaperCandidateEligibility`;
- exact UUID5 semantic identities and UTF-8 length framing;
- canonical Decimal/JSON transport;
- fixed v1 five-session policy;
- intrinsic consecutive-session/window validation;
- package exports;
- focused tests;
- mechanically required current-inventory/certification bookkeeping.

The checkpoint reads no real D1R7/D1R8/D1R9 evidence and creates no provider,
scheduler, credential, paper, broker, D2, promotion, or live effect.

## Certification state

The previous accepted canonical FULL remains historical evidence for the
c522 predecessor only:

```text
HEAD     c5225d8f3f584eb0eb60d62e5381f1caa3c56cb2
TREE     bf7019b1610c29563282ccb5f19be2bcb6501849
cases    12,354
passed   12,351
skipped  3
failed   0
errors   0
elapsed  287.176 s
```

144-A added one current FULL module and refreshed timing/inventory topology:

```text
FULL       187 modules
Robinhood  101 modules
LEGACY     222 modules
EXHAUSTIVE 409 modules
```

CI #638 ran the four broad source-gate shards successfully. That is source-gate
admission evidence, not a replacement canonical FULL certification.

Because 144-B is the immediately adjacent source-only successor and no protected
effect, merge, release, or production-readiness boundary is crossed between
144-A and 144-B, the pending FULL obligation is intentionally **batched through
144-B**. Run one fresh canonical FULL on the final accepted 144-A+B source
before the next protected multi-session paper-soak boundary. Do not run FULL
twice on adjacent source-only checkpoints.

## Architecture 144-B — immediate next source milestone

144-B is the separately reviewed external-evidence verification and positive
builder/verifier composition.

It must:

- independently verify the accepted Architecture-142 chain;
- independently verify the complete Architecture-143 compatibility proof;
- verify complete canonical D1R9/D1R8 evidence supplied by a reviewed
  acquisition boundary;
- require exact session, terminal classification, source, contract, strategy,
  symbol, configuration, and production-source agreement;
- reject partial/ambiguous/noncanonical evidence;
- construct verified session observations only after complete verification;
- construct positive eligibility only after five exact consecutive qualifying
  published regular sessions with at least one `PAPER_EXECUTED`.

144-B must remain pure with respect to evidence acquisition and operational
effects. It must not gain filesystem/scheduler/provider/broker authority merely
to obtain parser semantics.

## Unattended paper-trading readiness

Architecture 134 already defines the operational sequence:

```text
134-E  exactly one unattended integration session + independent reconciliation
134-F  fresh multi-session live-paper soak + end-of-window review
```

The accepted Monday 2026-10-19 D1R9 run satisfied the intended 134-E one-session
unattended proof:

```text
D1R9 FINAL / NO_SIGNAL
sha256 dcd41df103ad7afc549b7fa0c19ea844b98e0aa013de26e4203a532c087a8f81
D1R8 FINAL / NO_SIGNAL
sha256 11834d8693a236f1ff813dfe7f6be3076a79e4c6d171421a2ae08deb07ea2656
scheduler reconciliation MATCH
```

That proves the unattended operational path can complete one session safely. It
does **not** by itself authorize a fresh multi-session soak.

The next protected operational boundary after 144-B + final canonical FULL is
Architecture 134-F: a fresh multi-session paper soak with end-of-window review.
That soak validates scheduling/restart/idempotency and operational behavior. The
Architecture-144 five-session policy then provides the first research eligibility
gate over verified paper-session observations.

The frozen v1 research eligibility policy is:

```text
required_session_count = 5
required_paper_executed_count = 1
require_consecutive_published_regular_sessions = true
qualifying_terminal_classifications = ("NO_SIGNAL", "PAPER_EXECUTED")
```

Five sessions are a qualification/eligibility boundary, not enough evidence by
themselves to conclude long-run profitability.

## Protected and safety boundaries

- Real-money trading remains **NO-GO**.
- The Monday D1R9 authority is consumed and is not retried.
- 144-A and 144-B source work grant no operational authority.
- The future 134-F multi-session soak is a separately reviewed protected effect
  boundary.
- No source/CI/FULL result alone authorizes provider, scheduler, credential,
  paper, broker, D2, promotion, or live effects.
- `PAPER_CANDIDATE` materialization and human promotion remain later
  architectures.

## Active work

### Now

Architecture 144-B source implementation on the accepted 144-A feature lineage.

### Then

One fresh canonical FULL on the final accepted 144-A+B exact source.

### Then

Architecture 134-F protected preflight/authorization for a fresh multi-session
unattended paper soak, followed by end-of-window reconciliation and
Architecture-144 eligibility evaluation.

### Later

Continue paper observation long enough to evaluate performance stability beyond
the five-session qualification minimum before any promotion decision.
Restricted live trading remains unavailable.

## History and deep-reference pointers

Use [docs/history/INDEX.md](history/INDEX.md) for targeted historical
reconstruction. Closed D1R9/integration detail is preserved in
[the 2026-10-19 compact record](history/2026-10-19-d1r9-no-signal-and-safe-side-integration.md).
