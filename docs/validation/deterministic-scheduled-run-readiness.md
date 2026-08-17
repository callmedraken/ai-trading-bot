# Deterministic scheduled-run readiness validation

## Scope

Focused tests exercise the five UUID5 identity domains, strict immutable
attempt/selection records, explicit XNYS schedule fixtures, snapshot
eligibility, classification precedence, operation gates, and no-side-effect
behavior. They use only in-memory explicit evidence.

## Identity coverage

Reviewed vectors pin:

| Identity | UUID |
| --- | --- |
| scheduled session | `8de01536-2392-55bd-b8fe-17eae04aa816` |
| scheduled launch | `799b0440-a7de-51fb-bc16-743cbf4a9b48` |
| capture attempt | `81451a19-16ee-5a60-a28b-4349159d634b` |
| snapshot selection | `a9adff87-4f36-59ad-bb91-1c4730cfefc1` |
| caller-idempotency key | `01bf6713-a24f-56d3-b359-8d7c4f9f55bf` |

Tests prove launch retry changes only the launch identity, capture retry changes
the attempt but not session identity, repeated approved material remains stable,
and changed head/configuration evidence changes downstream authority. Identity
derivation remains unchanged under a hostile ambient Decimal context and model
material contains no path field.

## Schedule and capture coverage

The explicit fixture covers the July 2, 2026 XNYS early close, the July 3
observed holiday, and the next regular session on July 6. Missing coverage is
rejected. Tests classify capture-too-early, open-window/no-attempt, deadline
expiry, active backoff, and exhausted attempts.

Snapshot tests cover target mismatch, ordered-universe mismatch, terminal
chronology failure, future skew, staleness, duplicate eligible captures,
conflicting ordinals, and selection-record mismatch. The normal fixture uses a
sequence-two terminal and proves the selected snapshot is bound to that exact
head; changed terminal evidence derives a different selection.

## Operation coverage

The complete passing fixture reaches `READY` only with coordinator `PENDING`
and every scheduler gate passing. Separate tests prove:

- `PENDING` without selection is not ready;
- manual disable and unhealthy gates block;
- operation credentials block;
- conflicts suppress manual-review, blocked, completed, and not-ready states;
- verified transition without receipt requires review;
- failed receipt requires review;
- staging requires review;
- completely represented completion classifies `ALREADY_COMPLETED`;
- changed deterministic caller material conflicts.

## Purity coverage

Sentinels replace file opening, environment lookup, sockets, and the system
clock while the evaluator runs. A passing result proves those surfaces are not
used. The API exposes no output path and performs no filesystem mutation,
provider/broker call, process launch, pointer advancement, operation execution,
retry, sleep, or background loop.

## Required regressions

Completion requires:

```text
python -m pytest tests/runtime/test_scheduled_readiness.py
python -m pytest <related lineage-head, snapshot, operation-inspection, receipt tests>
python -m pytest
ruff check .
ruff format --check .
git diff --check
```

The official-hours artifact itself is not validated against an external
exchange source. Tests validate only the strict contract and reviewed explicit
fixtures; official content authority remains operationally deferred.
