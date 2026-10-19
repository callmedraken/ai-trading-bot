# Architecture 144 / RCL-7 — Research Strategy Paper-Candidate Eligibility Plan

Status: **DESIGN FROZEN; source implementation is the next safe-side
milestone.**

This validation plan freezes the pure Architecture-144 eligibility boundary.
It does not implement Architecture 144, acquire production evidence, create a
paper candidate, authorize promotion, or grant any operational authority.

## Validation objective

Validate that the future Architecture-144 implementation can create positive
`ResearchStrategyPaperCandidateEligibility` evidence only when all of the
following are true:

1. the exact accepted Architecture-142 strategy-native chain has been
   externally replay-verified;
2. the complete Architecture-143 compatibility proof has been externally
   verified with independently supplied 142 inputs;
3. each of exactly five consecutive published XNYS regular sessions has a
   complete, canonical, independently verified D1R9/D1R8 terminal observation;
4. each session terminal is exactly `NO_SIGNAL` or `PAPER_EXECUTED`; and
5. at least one session is fully acknowledged `PAPER_EXECUTED`.

Any mismatch, incomplete evidence, ambiguous acknowledgement, nonconsecutive
session sequence, rejected terminal, or missing execution evidence must raise
and produce no eligibility artifact.

## Exact admission and scope

The design-freeze checkpoint is admitted from:

```text
worktree F:\AI\ai-trading-bot
branch   develop
upstream origin/develop
starting HEAD  69d78d41da6c38ed3b7ae9751c54b02258b2934f
starting TREE  0a88d4f1b349fa2460d78f809423330209a77d87
```

The exact intended documentation paths are:

```text
docs/architecture/144-research-strategy-paper-candidate-eligibility.md
docs/validation/arch144-research-strategy-paper-candidate-eligibility-plan.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

No `src/**`, `tests/**`, `scripts/**`, `.github/**`, workflow YAML, D1R9,
provider, credential, scheduler, paper, broker, D2, live, or historical
architecture file belongs to this checkpoint. No Architecture-144 feature
implementation branch is created here.

## Frozen lifecycle and policy checks

The validation record must preserve the exact lifecycle:

```text
EXPERIMENTAL -> BACKTESTED -> WALK_FORWARD_PASSED -> SHADOW
-> PAPER_CANDIDATE -> AWAITING_HUMAN_PROMOTION
```

Architecture 141 remains `SHADOW` / `NOT_ESTABLISHED`. Architecture 144 does
not add a stage setter, materialize `PAPER_CANDIDATE`, create
`AWAITING_HUMAN_PROMOTION`, approve a human promotion, or choose a production
strategy.

The only accepted paper-soak policy is:

```text
required_session_count = 5
required_paper_executed_count = 1
require_consecutive_published_regular_sessions = true
qualifying_terminal_classifications = ("NO_SIGNAL", "PAPER_EXECUTED")
```

The validation must explicitly reject `RISK_REJECTED`, `SESSION_MISSED`,
`BLOCKED`, and `INDETERMINATE` as qualifying window members. It must state that
`NO_SIGNAL` supplies coverage only and that only fully acknowledged
`PAPER_EXECUTED` supplies execution-dependent evidence. No automatic retry or
new soak window is allowed.

## Frozen artifact assertions

The implementation validation must preserve these exact artifact families,
schemas, identity versions, namespaces, and fields.

### Session observation

```text
type              ResearchStrategyPaperSessionObservation
schema            research-strategy-paper-session-observation/v1
identity version  research-strategy-paper-session-observation-identity/v1
namespace         b39bc4f6-4de1-5dd3-b9ec-286702cd744b
```

```text
schema
observation_id
compatibility_proof_id
production_target_id
target_session_date
production_contract_id
d1r9_source_head
d1r9_source_tree
d1r8_source_head
d1r8_source_tree
d1r9_journal_sha256
d1r8_journal_sha256
terminal_classification
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config
production_source_head
production_source_tree
```

Canonical journal bytes are verifier inputs only; they are not embedded
observation fields.

### Soak policy

```text
type              ResearchStrategyPaperSoakPolicy
schema            research-strategy-paper-soak-policy/v1
identity version  research-strategy-paper-soak-policy-identity/v1
namespace         d0124aa1-3a8e-577f-9848-977fa0adb83a
```

```text
schema
policy_id
required_session_count
required_paper_executed_count
require_consecutive_published_regular_sessions
qualifying_terminal_classifications
```

### Eligibility

```text
type              ResearchStrategyPaperCandidateEligibility
schema            research-strategy-paper-candidate-eligibility/v1
identity version  research-strategy-paper-candidate-eligibility-identity/v1
namespace         28ed63ec-8f37-59ce-aad8-57741a645832
```

```text
schema
eligibility_id
compatibility_proof_id
production_target_id
policy_id
observation_ids
first_session_date
last_session_date
paper_executed_count
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config
research_strategy_source_head
research_strategy_source_tree
production_source_head
production_source_tree
eligibility_source_head
eligibility_source_tree
```

The eligibility artifact is positive-only. There is no eligibility boolean;
artifact existence after complete verification is the assertion. The five
observation IDs must be chronological and cover exactly five consecutive
published regular sessions.

All identities must use versioned, length-framed UTF-8 semantic material and
must not use JSON bytes, `repr()`, Python hashes, paths, clocks, UUID4, object
identity, locale, or ambient state. Canonical parsing must reject duplicate,
unknown, missing, noncanonical, float, nonfinite, bool-as-int, or otherwise
ambiguous values according to the established deterministic domain rules.

## Required external verification matrix

The future builder and verifier must independently supply and externally
reconcile the complete Architecture-142 chain and accepted Architecture-143
verifier boundary. A parsed proof is never sufficient.

For every candidate observation, tests must require:

- complete canonical D1R9 terminal evidence;
- complete canonical D1R8 terminal evidence;
- exact session-date agreement;
- exact terminal-classification agreement;
- exact accepted D1R9/D1R8 source HEAD/TREE identities;
- no prefix, partial, truncated, terminal-looking, or ambiguous journal;
- exact existing `ProductionStrategyContract` recovered from evidence;
- exact contract target date;
- exact production schema, strategy family, strategy version, `Symbol`, and
  `MovingAverageCrossoverConfig` match;
- exact production source HEAD/TREE match; and
- equality of all non-date production-contract semantics across the five
  observations.

Required negative cases include altered journal bytes/hash, source drift,
session mismatch, D1R8/D1R9 classification mismatch, missing contract,
contract-date mismatch, schema/family/version/config/symbol mismatch, an
unacknowledged intent, a partial terminal, ambiguous child acknowledgement,
`RISK_REJECTED`, `SESSION_MISSED`, `BLOCKED`, and `INDETERMINATE`.

Required soak-window cases include fewer than five sessions, five nonconsecutive
published sessions, a qualifying sequence with no `PAPER_EXECUTED`, one or
more `NO_SIGNAL` sessions with no execution evidence, and a valid five-session
sequence containing at least one fully acknowledged `PAPER_EXECUTED`.

The valid case must create one positive eligibility artifact only after all
five observations and the complete 142/143 evidence chain have been verified.
Every negative case must fail before artifact construction and must not invoke
any external acquisition or operational boundary.

## Purity and zero-effect checks

The safe-side source implementation must remain pure and must not read the
production D1R9/D1R8 journals, production SQLite, credentials, provider,
Robinhood, broker, scheduler, ACL, paper state, D2 state, or live state.
Synthetic/fake canonical evidence is allowed only in tests.

The exact effect assertions are:

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
ROBINHOOD_READS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
PAPER_CANDIDATES_CREATED=0
D1_OPERATIONS=0
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
D1R9_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

Static/capability checks must reject `build_production_strategy`, production
contract creation, lifecycle mutation, D1/D1R9 invocation, journal access,
filesystem/network/provider/credential/broker/scheduler/SQLite/GUI/subprocess
capabilities, current-clock acquisition, and randomness.

## Monday D1R9 boundary

The Monday `2026-10-19` D1R9 authorization remains ACTIVE / CONSUMED and
independent. This design checkpoint must not re-authorize it, manually invoke
D1R7/D1R8, mutate its scheduler task, inspect its durable evidence, or infer
an observation before separately reviewed terminal evidence exists.

The future validation may model Monday only with synthetic canonical evidence.
The real result, whether `NO_SIGNAL`, `PAPER_EXECUTED`, `RISK_REJECTED`,
`SESSION_MISSED`, `BLOCKED`, or `INDETERMINATE`, never authorizes retry or
materialization by itself.

## Design-only verification

For this checkpoint, run only:

- exact diff inspection;
- verification that exactly the four intended documentation paths changed;
- searches for accidental claims that `PAPER_CANDIDATE` already exists;
- searches for accidental claims that `AWAITING_HUMAN_PROMOTION` or human
  approval already exists;
- searches for accidental D1R9, scheduler, provider, credential, paper,
  broker, D2, or live authority/effect claims;
- `git diff --check`; and
- any explicitly required cheap docs/static check.

Do not run pytest merely because this is a new architecture document. Do not
run FULL, ROBINHOOD, LEGACY, or EXHAUSTIVE certification. Do not acquire or
inspect real D1R9/D1R8 evidence.

## Publication and stop conditions

This is one logical docs-only checkpoint. Before commit, prove the index was
initially clean, stage exactly the four paths, print the staged filename set,
inspect the cached diff, and run `git diff --cached --check`. Create one atomic
commit with:

```text
docs: freeze Architecture 144 paper eligibility design
```

Push `develop` to `origin/develop` once. Poll the resulting push-triggered CI
admission attempt to terminal. Do not manually dispatch a second run. If CI
fails, preserve the evidence and stop; any correction is a separately
declared corrective checkpoint.

The design checkpoint is accepted only if the final tree contains exactly the
four intended documentation changes, no source/tests/scripts/workflow YAML
changed, no local FULL/ROBINHOOD ran, and all effect counters remain zero.

## Next reviewed boundary

After ChatGPT exact review accepts this design and its atomic docs-only
publication, the next safe-side milestone is Architecture-144 source
implementation planning/admission. That checkpoint must separately resolve
the exact executable predecessor and public D1R9/D1R8 evidence-parser
authority. It must not broaden into evidence acquisition, paper-candidate
materialization, human promotion, production selection, or any protected
effect.

Real-money trading remains **NO-GO**.
