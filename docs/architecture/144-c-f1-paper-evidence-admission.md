# Architecture 144-C — F1 paper-evidence admission successor

Status: **DESIGN FROZEN against accepted Architecture 134-F1 source. Implementation is next.**

Architecture 144-C adds a separate pure current-lineage evidence-admission
successor for Architecture 134-F1. It does not reinterpret, loosen, or replace
Architecture-144 v1.

## Exact predecessor and provenance pins

Implementation predecessor:

```text
branch  develop
HEAD    f47deac55e22f5a1f215bed69b3429038d7babb0
TREE    6a5e3319729e2d1e4b034631dd1d2edb99ccaa4f
```

Accepted F1 evidence-authority source:

```text
branch  feature/robinhood-production-paper-134f-five-session-soak
HEAD    b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE    e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

Accepted F1 implementation blobs relevant to pure evidence replay:

```text
five_session_soak_store.py   3813837e8d10ee2b19150405143704a7f03d474f
five_session_soak.py         9de15257fc9b6fe97e90314450b097849ff81320
five_session_soak_child.py   6afcdfe42ac1691bc477efcfb4764c227a0c1bc2
```

The F1 evidence provenance is the accepted F1 feature HEAD/TREE above, not the
later develop merge commit. The develop identity is only the implementation
predecessor for 144-C.

Accepted F1 child-source pins remain:

```text
D1R7
HEAD 30322c49b13b80af8d20acee4bdb1efd83d86260
TREE b7dc7f054fca50c3ab784505f264b6f716a45dff

D1R8
HEAD aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2
TREE fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f
```

## Frozen v1 compatibility rule

Architecture-144 v1 remains byte-for-byte and behaviorally frozen.

At minimum these accepted v1 implementation blobs are immutable for 144-C:

```text
research_strategy_paper_candidate_eligibility.py
fd6b0ad650fb3fb97f587deb7cffc7286e685813

research_strategy_paper_evidence_verification.py
915bdd84bee3ad0b57efcafb0a78da01fce94e66
```

144-C must not modify those files, their v1 schemas, namespaces, identity
material, canonical JSON bytes, D1R9/D1R8 source pins, builders, verifiers, or
terminal semantics. Truthful F1 evidence must continue to fail the v1 D1R9
source-binding contract.

The existing public `ResearchStrategyPaperSoakPolicy` v1 is reused unchanged.
A provenance-version change does not create a policy-version change.

Its fixed meaning remains:

```text
required_session_count = 5
required_paper_executed_count = 1
require_consecutive_published_regular_sessions = true
qualifying_terminal_classifications = ("NO_SIGNAL", "PAPER_EXECUTED")
```

## V2 artifact families

144-C adds separate V2 artifacts rather than overloading v1.

### Session observation V2

Type:

`ResearchStrategyPaperSessionObservationV2`

Schema:

`research-strategy-paper-session-observation/v2`

Identity version:

`research-strategy-paper-session-observation-identity/v2`

Namespace:

`8769f313-42dc-512f-91b2-e0299f6c9200`

The namespace is UUID5(NAMESPACE_URL,
`https://github.com/callmedraken/ai-trading-bot/research-strategy-paper-session-observation/v2`).

Exact fields:

```text
schema
observation_id
compatibility_proof_id
production_target_id
target_session_date
production_contract_id
paper_authority_kind
paper_authority_schema
paper_authority_source_head
paper_authority_source_tree
authority_parent_id
authority_parent_journal_sha256
authority_child_ordinal
authority_child_id
authority_child_journal_sha256
d1r7_source_head
d1r7_source_tree
d1r7_evidence_sha256
d1r8_source_head
d1r8_source_tree
d1r8_evidence_sha256
terminal_classification
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config
production_source_head
production_source_tree
```

Fixed F1 authority values are:

```text
paper_authority_kind        ARCH134_F1
paper_authority_schema      arch134-f1-five-session-soak/v1
paper_authority_source_head b59ad3b44540a55a30f612d5c4e3e38e26a95b02
paper_authority_source_tree e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

The observation identity material is each UTF-8 text item independently framed
as `<byte-length>:<text>`, concatenated with no separator, in this exact order:

```text
identity version
schema
compatibility_proof_id
production_target_id
target_session_date
production_contract_id
paper_authority_kind
paper_authority_schema
paper_authority_source_head
paper_authority_source_tree
authority_parent_id
authority_parent_journal_sha256
authority_child_ordinal
authority_child_id
authority_child_journal_sha256
d1r7_source_head
d1r7_source_tree
d1r7_evidence_sha256
d1r8_source_head
d1r8_source_tree
d1r8_evidence_sha256
terminal_classification
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config.short_window
strategy_config.long_window
canonical_decimal(strategy_config.desired_quantity)
production_source_head
production_source_tree
```

`observation_id` is derived and excluded from its own material.

### Candidate eligibility V2

Type:

`ResearchStrategyPaperCandidateEligibilityV2`

Schema:

`research-strategy-paper-candidate-eligibility/v2`

Identity version:

`research-strategy-paper-candidate-eligibility-identity/v2`

Namespace:

`98822733-db5a-5382-b362-a441861d56e1`

The namespace is UUID5(NAMESPACE_URL,
`https://github.com/callmedraken/ai-trading-bot/research-strategy-paper-candidate-eligibility/v2`).

Exact fields:

```text
schema
eligibility_id
compatibility_proof_id
production_target_id
policy_id
paper_authority_kind
paper_authority_schema
paper_authority_source_head
paper_authority_source_tree
authority_parent_id
authority_parent_journal_sha256
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

Identity material uses the same independent UTF-8 length framing in this exact
order:

```text
identity version
schema
compatibility_proof_id
production_target_id
policy_id
paper_authority_kind
paper_authority_schema
paper_authority_source_head
paper_authority_source_tree
authority_parent_id
authority_parent_journal_sha256
len(observation_ids)
each observation_id in chronological order
first_session_date
last_session_date
paper_executed_count
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config.short_window
strategy_config.long_window
canonical_decimal(strategy_config.desired_quantity)
research_strategy_source_head
research_strategy_source_tree
production_source_head
production_source_tree
eligibility_source_head
eligibility_source_tree
```

`eligibility_id` is derived and excluded from its own material.

The eligibility artifact remains positive-only. There is no eligibility boolean.

## Canonical representation

V2 follows the accepted deterministic domain rules:

- exact finite Decimal values only;
- canonical Decimal text identical to v1;
- canonical lowercase UUID strings;
- source HEAD/TREE as lowercase 40-hex;
- evidence digests as lowercase 64-hex;
- exact ISO dates;
- JSON integers are not bool;
- `strategy_config` has only `short_window`, `long_window`, and
  `desired_quantity`;
- canonical JSON uses `sort_keys=True`, separators `(",", ":")`,
  `allow_nan=False`, UTF-8, and no trailing newline;
- duplicate, unknown, missing, alternate-spelling, float, nonfinite, reordered,
  or otherwise noncanonical representations fail closed.

Serialized evidence bytes are not UUID material. Their SHA-256 digests are
semantic provenance fields. Paths, clocks, file metadata, Python hashes,
`repr()`, object identity, UUID4/randomness, locale, and ambient Decimal
context are forbidden identity inputs.

## Pure supplied-evidence verification

144-C consumes supplied bytes/objects only. It never acquires production
evidence itself.

For one observation the caller supplies:

```text
F1 parent journal bytes
matching F1 child journal bytes
D1R7 evidence bytes
D1R8 evidence bytes
accepted Architecture-142/143 proof objects
ProductionStrategySemanticTarget
qualification/proof source pins
```

The pure verifier must independently establish all of the following before
constructing a V2 observation:

1. the F1 parent journal is canonical, source-pinned to accepted F1, and ends
   `FINAL / COMPLETED`;
2. the parent FINAL proof binds exactly five ordered reconciled child summaries,
   scheduler `MATCH`, and the exact pre-FINAL parent-prefix digest;
3. the selected child ordinal is 1 through 5 and its target equals the parent's
   frozen target at that ordinal;
4. child identity, child-journal digest, and immutable grant-prefix digest match
   the selected parent summary;
5. child bytes replay canonically to the same terminal classification and effect
   accounting;
6. supplied D1R7 bytes hash to the saved D1R7 proof and satisfy the fixed D1R7
   source, target, policy, and production-contract binding;
7. supplied D1R8 bytes hash to the saved D1R8 proof, bind the same D1R7 proof and
   target, reproduce the saved terminal classification, and reproduce the full
   saved D1R8 effect counters;
8. the complete Architecture-142/143 chain independently verifies;
9. the recovered production contract matches the verified semantic target; and
10. all strategy, symbol, config, production-source, source-pin, and target
    semantics agree exactly.

The parser/verifier must be implemented as an independent pure V2 successor. It
must not import private helpers from v1 and must not import or invoke F1 host,
scheduler, bridge, child-process, provider, credential, filesystem-acquisition,
or other operational surfaces merely to obtain parser semantics.

## Observation and eligibility semantics

A complete F1 child terminal of `NO_SIGNAL`, `RISK_REJECTED`, or
`PAPER_EXECUTED` may create a verified V2 observation only when the complete
D1R7/D1R8 evidence above is present and exact.

`SESSION_MISSED`, `BLOCKED`, and `INDETERMINATE` do not create positive
V2 observations.

For positive eligibility:

- exactly five V2 observations are required;
- ordinals must be exactly 1,2,3,4,5;
- all five must bind the same exact F1 parent ID and full parent-journal digest;
- all five must bind the same authority kind/schema/source HEAD/TREE;
- target dates must be exactly the parent's five frozen ordered targets and five
  consecutive published regular sessions;
- production target, strategy semantics and production source must remain stable;
- every terminal must be `NO_SIGNAL` or `PAPER_EXECUTED`;
- at least one must be `PAPER_EXECUTED`.

`RISK_REJECTED` is a valid verified observation but is nonqualifying for the
window, exactly as in v1.

## Purity and effect boundary

144-C is a pure `experiments` successor. Its implementation and tests must
establish:

```text
FILESYSTEM_READS=0
FILESYSTEM_WRITES=0
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
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
D1R9_OPERATIONS=0
F1_OPERATIONS=0
LIVE_EFFECTS=0
```

No 144-C source, source gate, or certification result authorizes protected
134-F preflight or the real five-session soak.

Real-money trading remains **NO-GO**.

## Implementation boundary

Primary implementation branch:

`feature/test-suite-arch144-c-f1-paper-evidence-admission-current`

Canonical worktree:

`F:\AI\worktrees\ai-trading-bot-arch144-c-f1-paper-evidence-admission-current`

Primary new source surfaces are expected to be:

```text
src/trading_bot/experiments/research_strategy_paper_candidate_eligibility_v2.py
src/trading_bot/experiments/research_strategy_f1_paper_evidence_verification.py
tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py
tests/experiments/test_research_strategy_f1_paper_evidence_verification.py
```

The public experiments export surface may be updated. Mechanically required
checkpoint/current-inventory/timing/pin tests may also be updated. The two frozen
v1 implementation files above must not change.

The source checkpoint name is:

`arch144-c-f1-paper-evidence-admission`

It is source-only:

```text
preflight None
execute   None
```

No canonical ROBINHOOD/FULL profile is selected in advance. The branch is
already admitted by the existing `feature/test-suite-*` source-gate family.
Use focused tests plus the normal push-triggered source gate. ChatGPT selects an
additional canonical profile only if the final changed surface materially
requires one. FULL is not automatic.

## Sequencing

Required order:

```text
144-C design freeze
-> 144-C source implementation + focused verification
-> one atomic feature publication
-> terminal source-gate CI
-> ChatGPT exact-source acceptance
-> only then protected 134-F preflight review
-> only then, if separately admitted, real five-session soak
-> end-of-window reconciliation
-> supplied-evidence V2 eligibility evaluation
```

The design freeze itself performs no operational effect.
