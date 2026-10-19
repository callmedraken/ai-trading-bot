# Architecture 144 / RCL-7 — Research Strategy Paper-Candidate Eligibility Plan

Status: **DESIGN FROZEN; C1 source-readiness clarification recorded; 144-A is
the next safe-side milestone.**

This validation plan freezes the pure Architecture-144 eligibility boundary.
It does not implement Architecture 144, acquire production evidence, create a
paper candidate, authorize promotion, or grant any operational authority.

## C1 source-readiness validation contract

This corrective checkpoint preserves the existing Architecture-144 schemas,
namespaces, exact field sets, lifecycle, frozen v1 policy, zero-effect
boundary, and Monday D1R9 separation. It freezes only the byte-level identity,
canonical transport, parser rejection, source-lineage, and 144-A/144-B
implementation boundaries required before executable source work.

Every UUID5 semantic text item is independently encoded as
`<UTF-8 byte length>:<UTF-8 text>`; framed items are concatenated with no
delimiter or trailing material. Artifact JSON bytes, `repr()`, Python hashes,
object identity, paths, clocks, locale, UUID4/randomness, and ambient Decimal
context are forbidden identity inputs. Canonical Decimal text requires an
exact finite `Decimal`, `format(value, "f")`, removal of trailing fractional
zeroes and a trailing decimal point, and normalization of `""` and `"-0"`
to `"0"`.

The exact UUID5 material is frozen as follows; each listed item is framed in
the stated order and the derived ID is excluded from its own input.

### Observation

```text
namespace b39bc4f6-4de1-5dd3-b9ec-286702cd744b
research-strategy-paper-session-observation-identity/v1
schema
str(compatibility_proof_id)
str(production_target_id)
target_session_date.isoformat()
str(production_contract_id)
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
str(symbol)
str(strategy_config.short_window)
str(strategy_config.long_window)
canonical_decimal(strategy_config.desired_quantity)
production_source_head
production_source_tree
```

`observation_id` is derived and excluded. A successfully externally verified
observation may be exactly `NO_SIGNAL`, `RISK_REJECTED`, or
`PAPER_EXECUTED`. `RISK_REJECTED` is a verified observation but is rejected by
the v1 soak policy. `SESSION_MISSED`, `BLOCKED`, and `INDETERMINATE` do not
produce a positive v1 observation because they do not establish a complete
D1R8-backed boundary; this does not authorize retries.

### Fixed policy

```text
namespace d0124aa1-3a8e-577f-9848-977fa0adb83a
research-strategy-paper-soak-policy-identity/v1
schema
str(required_session_count)
str(required_paper_executed_count)
"true"
str(len(qualifying_terminal_classifications))
each qualifying_terminal_classification in exact tuple order
```

The tuple is exactly `("NO_SIGNAL", "PAPER_EXECUTED")`; the lowercase
literal `"true"` is the identity spelling of the frozen boolean `true` value.
`policy_id` is derived and excluded.

### Eligibility

```text
namespace 28ed63ec-8f37-59ce-aad8-57741a645832
research-strategy-paper-candidate-eligibility-identity/v1
schema
str(compatibility_proof_id)
str(production_target_id)
str(policy_id)
str(len(observation_ids))
each str(observation_id) in exact chronological order
first_session_date.isoformat()
last_session_date.isoformat()
str(paper_executed_count)
production_strategy_schema
strategy_id
strategy_version
str(symbol)
str(strategy_config.short_window)
str(strategy_config.long_window)
canonical_decimal(strategy_config.desired_quantity)
research_strategy_source_head
research_strategy_source_tree
production_source_head
production_source_tree
eligibility_source_head
eligibility_source_tree
```

`eligibility_id` is derived and excluded. All three artifacts use their exact
existing field sets in canonical JSON with `sort_keys=True`, separators
`(",", ":")`, `allow_nan=False`, and no trailing newline. UUIDs are canonical
lowercase strings; dates are exact `YYYY-MM-DD`; symbols are `str(symbol)`;
the config has only `short_window`, `long_window`, and `desired_quantity`; the
window values are JSON integers and never bool; desired quantity is canonical
Decimal text and never float; ordered arrays preserve chronology or the frozen
policy tuple; the consecutive-session flag is a JSON boolean; journal hashes
are lowercase 64-hex; and source HEAD/TREE values are lowercase 40-hex.

Pure parsing rejects unknown, missing, or duplicate fields, alternate UUID/date
spelling, floats, bool-as-int, nonfinite or noncanonical Decimal text,
alternate config fields, and reordered/noncanonical bytes when exact canonical
roundtrip is required.

### Lineage and staged implementation boundary

The future executable predecessor is the final accepted Architecture-143/R3I-
C1 descendant:

```text
HEAD c5225d8f3f584eb0eb60d62e5381f1caa3c56cb2
TREE bf7019b1610c29563282ccb5f19be2bcb6501849
```

Accepted D1R8 parser authority is:

```text
branch feature/robinhood-production-paper-d1-session-execution
HEAD   aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2
TREE   fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f
```

Its parser is
`src/trading_bot/review_paper/d1_session_execution_store.py`, blob
`e35b0d528cecb396d5b7ffadcd158647becddba5`. Accepted D1R9 parser/store
authority is:

```text
branch feature/robinhood-production-paper-d1-arbitrary-time-supervisor
HEAD   efd1e6763dc4663d9c4b2444e785eb1c32adf8e8
TREE   25a962daf3922c4226c7e395eba8613e1b03bbaf
```

Its canonical store/parser is
`src/trading_bot/review_paper/d1_session_supervisor_store.py`, blob
`a0ebf56afa089c245dbaaebcf2182bdb9486bf49`; accepted reconciliation/proof
logic is `src/trading_bot/review_paper/d1_session_supervisor.py`, blob
`b35d47931ceb0a861b6e47ab6fb7853ac1f674ce`. D1R9 files are not present in
the c522 predecessor or develop, and no merge/cherry-pick resolves that split.

144-A is limited to the three artifact types, their constants and exact
identities, strict canonical JSON, fixed v1 policy, intrinsic/self-consistency
validation, pure parsing, exports, focused tests, and mechanically required
inventory/current-pin bookkeeping. It must not import/copy D1R9 operational
modules, parse real D1R9/D1R8 evidence, claim externally verified observations,
provide positive builders, acquire evidence, read files, invoke D1/D1R7/D1R8/
D1R9, create `PAPER_CANDIDATE`, or promote. Parsed objects are evidence
containers only. 144-B is a separately reviewed external evidence verifier and
positive builder composition; it must resolve a pure D1R9 verifier composition
without importing/copying filesystem, scheduler, or other effectful surfaces
just for parser semantics. C1 and 144-A make no decision about that pure
composition.

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
