# Architecture 144 / RCL-7 — Research Strategy Paper-Candidate Eligibility

Status: **DESIGN FROZEN; source implementation is the next safe-side
milestone.**

Architecture 144 is the separately reviewed successor permitted by the
accepted Architecture-143 lifecycle boundary. It consumes the exact accepted
Architecture-142 strategy-native chain, a fully externally verified
`ResearchStrategyProductionCompatibilityProof`, canonical production-paper
session evidence, and one frozen paper-soak policy. It determines only whether
the strategy-native research path has positive paper-candidate eligibility
evidence.

This design does not materialize `PAPER_CANDIDATE`, create
`AWAITING_HUMAN_PROMOTION`, promote anything, create a new
`ProductionStrategyContract`, or select or replace the production strategy.
Human promotion remains a later explicit boundary. Real-money trading remains
**NO-GO**.

## Frozen lifecycle boundary

The existing conceptual lifecycle remains exactly:

```text
EXPERIMENTAL
-> BACKTESTED
-> WALK_FORWARD_PASSED
-> SHADOW
-> PAPER_CANDIDATE
-> AWAITING_HUMAN_PROMOTION
```

Architecture 144 does not mutate this vocabulary or add a generic stage setter.
The strategy-native Architecture-142/143 path does not reinterpret the old
Architecture-139/141 portfolio candidate. Architecture 141 remains permanently
at:

```text
stage  SHADOW
status NOT_ESTABLISHED
```

Architecture 143 remains semantic compatibility proof only. Architecture 144
produces positive eligibility evidence only. Actual `PAPER_CANDIDATE`
materialization is a later separately reviewed architecture, and
`AWAITING_HUMAN_PROMOTION` is later again. Human approval and promotion are not
part of this boundary.

## Frozen paper-soak policy v1

The only policy accepted by Architecture 144 is:

```text
required_session_count = 5
required_paper_executed_count = 1
require_consecutive_published_regular_sessions = true
qualifying_terminal_classifications = ("NO_SIGNAL", "PAPER_EXECUTED")
```

A qualifying window consists of exactly five consecutive published XNYS
regular sessions. Every session must have a qualifying clean terminal
classification, and at least one of the five sessions must be fully
acknowledged `PAPER_EXECUTED`.

`NO_SIGNAL` contributes session-soak coverage only. `PAPER_EXECUTED` is the
only classification that contributes execution-dependent evidence.
`RISK_REJECTED` is a safe consumed D1R9 outcome, but it does not qualify a
session inside the v1 window. `SESSION_MISSED`, `BLOCKED`, and `INDETERMINATE`
also reject the qualifying window. The policy does not start another window,
authorize another session, or retry anything automatically.

There is no caller-selected relaxation, override, alternate classification
set, or policy substitution. The required execution count is a minimum of one;
the observed `paper_executed_count` records the verified count in the exact
five-session window.

## Frozen artifact family

### ResearchStrategyPaperSessionObservation

Schema:

```text
research-strategy-paper-session-observation/v1
```

Identity version:

```text
research-strategy-paper-session-observation-identity/v1
```

UUID5 namespace:

```text
b39bc4f6-4de1-5dd3-b9ec-286702cd744b
```

The exact semantic field set is:

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

The observation identity uses the versioned semantic identity material above,
encoded as length-framed UTF-8 fields under the frozen UUID5 namespace. The
identity is semantic and deterministic. It must not use JSON/artifact bytes,
`repr()`, Python hashes, object identity, filesystem paths, clocks, UUID4,
locale, ambient configuration, or other ambient state. Canonical journal bytes
are verifier inputs and are not embedded observation fields.

`d1r9_journal_sha256` and `d1r8_journal_sha256` are evidence references, not
substitutes for independently verifying the complete canonical journals.
`production_contract_id` identifies the exact existing contract recovered from
accepted D1R8/D1R9 evidence; Architecture 144 never creates that contract.

### ResearchStrategyPaperSoakPolicy

Schema:

```text
research-strategy-paper-soak-policy/v1
```

Identity version:

```text
research-strategy-paper-soak-policy-identity/v1
```

UUID5 namespace:

```text
d0124aa1-3a8e-577f-9848-977fa0adb83a
```

The exact field set is:

```text
schema
policy_id
required_session_count
required_paper_executed_count
require_consecutive_published_regular_sessions
qualifying_terminal_classifications
```

The v1 policy has exactly the frozen values shown above. Its identity is the
versioned length-framed UTF-8 semantic policy material under the frozen UUID5
namespace. The policy is a fixed value, not a caller-controlled set of
thresholds or terminal classifications.

### ResearchStrategyPaperCandidateEligibility

Schema:

```text
research-strategy-paper-candidate-eligibility/v1
```

Identity version:

```text
research-strategy-paper-candidate-eligibility-identity/v1
```

UUID5 namespace:

```text
28ed63ec-8f37-59ce-aad8-57741a645832
```

This is positive-only eligibility evidence. Its exact semantic field set is:

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

`observation_ids` are the exact five observation IDs in chronological regular
session order. `first_session_date` and `last_session_date` are the bounds of
that ordered five-session window. The eligibility identity uses the frozen
versioned, length-framed UTF-8 semantic material and excludes no semantic
field except the derived `eligibility_id` itself.

There is no eligibility boolean. Existence of an eligibility artifact after
full verification is the positive assertion. Any mismatch raises and produces
no eligibility artifact.

## Required external verification boundary

Architecture 144 must never trust a parsed Architecture-143 proof by itself.
Before constructing or accepting any observation or eligibility artifact, the
eventual implementation must externally verify the complete Architecture-143
proof through its accepted public verifier and independently supplied
Architecture-142 chain.

For each paper-session observation, it must also externally verify the complete
canonical D1R9/D1R8 evidence and require all of the following:

- canonical D1R9 terminal evidence;
- canonical D1R8 terminal evidence;
- exact target-session agreement;
- exact D1R9/D1R8 terminal-classification agreement;
- exact accepted D1R9/D1R8 source identities;
- complete evidence, not a prefix, partial file, terminal-looking fragment, or
  ambiguous acknowledgement;
- the exact existing `ProductionStrategyContract` recovered from accepted
  evidence;
- `contract.target_session_date == observation.target_session_date`;
- exact production strategy schema match to the Architecture-143 target;
- exact strategy-family match;
- exact strategy-version match;
- exact `Symbol` match;
- exact `MovingAverageCrossoverConfig` match;
- exact production source HEAD match; and
- exact production source TREE match.

Across a qualifying five-session window, `target_session_date` is the only
production-contract semantic field expected to vary. No name, rank, metadata,
numeric coincidence, or other semantic approximation may substitute for exact
comparison.

The accepted D1R8/D1R9 contract already distinguishes the terminal evidence:
`NO_SIGNAL` consumes a session but does not prove execution;
`RISK_REJECTED` consumes a session but does not prove execution; and only a
fully acknowledged `FINAL / PAPER_EXECUTED` can satisfy the
execution-dependent soak prerequisite.

## Parsing is not authority

Canonical parsing proves only self-consistency. It does not prove that bytes
came from the actual durable host evidence. The safe-side Architecture-144
implementation remains pure and must not read production files, production
SQLite, the D1R9 journal, the D1R8 journal, credentials, scheduler state, or
provider state itself.

Actual acquisition of canonical D1R9/D1R8 bytes is a future separately
reviewed read-only evidence-acquisition boundary. The eventual source may use
synthetic or fake canonical evidence in tests, but it may not touch the real
D1R9 journal or any real production evidence during source validation.

## Monday D1R9 relationship

The existing D1R9 one-session authorization for Monday `2026-10-19` remains
**ACTIVE / CONSUMED** and independent of Architecture 144. This design does
not re-authorize it, create/run/update/delete/recreate its scheduler task, or
invoke D1R7/D1R8 manually. The task-owned supervisor continues independently.

Monday can become the first possible Architecture-144 session observation only
after durable terminal evidence exists and is separately reviewed. This design
checkpoint does not inspect or mutate that evidence.

If Monday ends `NO_SIGNAL`, it may later count as clean soak-session coverage
but not execution evidence. If it ends `PAPER_EXECUTED`, it may later count as
both clean coverage and the required execution evidence. `RISK_REJECTED`,
`SESSION_MISSED`, `BLOCKED`, and `INDETERMINATE` cannot qualify inside the v1
five-session window. None authorizes an automatic retry.

## No materialization or promotion

Architecture 144 must not:

- create a `ResearchStrategyCandidate` at stage `PAPER_CANDIDATE`;
- mutate any existing lifecycle artifact;
- create `AWAITING_HUMAN_PROMOTION`;
- create or select a `ProductionStrategyContract`;
- call `build_production_strategy`;
- choose a future production session;
- perform human approval or strategy promotion;
- modify production selection;
- arm D1 or invoke D1R9;
- create scheduler, provider, credential, paper-execution, broker, D2, or
  live authority; or
- read or mutate production evidence as part of the pure source boundary.

## Zero-effect contract

The design/source intent is exactly:

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

## Future source boundary

This checkpoint creates no executable Architecture-144 source. The next
source implementation must resolve its exact executable predecessor and the
accepted D1R9/D1R8 evidence-parser/verifier authority separately. It must not
silently merge unrelated branches, use the real D1R9 journal, or broaden this
design into evidence acquisition, paper-candidate materialization, promotion,
or production selection.

The implementation is expected to preserve the existing Architecture-142 and
143 schemas, identities, serialized bytes, and behavior. It must preserve
Architecture 141's `SHADOW` / `NOT_ESTABLISHED` meaning and the D1R8/D1R9
terminal distinction. Any future test fixtures must be synthetic and
canonical; no production evidence is a test fixture.

## Next reviewed boundary

The immediate next safe-side step after this design is accepted is
Architecture-144 source implementation planning/admission, subject to
ChatGPT's exact review of the executable predecessor, D1R9/D1R8 public
verifiers, source scope, and focused-test plan. No source implementation,
evidence acquisition, full certification, Robinhood certification, or
operational effect is part of this design freeze.

Real-money trading remains **NO-GO**.
