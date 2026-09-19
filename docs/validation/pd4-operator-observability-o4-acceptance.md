# PD4 Operator Observability O4 Acceptance

Status: **ACCEPTED SOURCE CHECKPOINT**

## Accepted identity and evidence

```text
branch: feature/pd4-operator-observability
HEAD: 2fab48301530a89df21391c047f848eb3fd97272
TREE: f8df06396a5203367bb9b0abdbcfd167bfa46d67
focused pytest: 266 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
git diff --cached --check: PASS
worktree: CLEAN
```

The focused verification above is the operator-supplied acceptance evidence,
not a new run in this documentation checkpoint. On 2026-09-19, the exact local
HEAD/tree, branch, origin, upstream tracking ref, empty index and clean worktree
were independently checked. Origin is callmedraken/ai-trading-bot. The O4 source
diff from accepted O3 was inspected, including the shared evaluator, adapter,
presentation models, page and associated regression coverage.

## Scope and boundary

Strategy explanation is read-only. Both the strategy and diagnostic adapter use
`evaluate_moving_average_crossover_closes`; MA3/MA5 arithmetic belongs to the
source-owned strategy evaluator, not the Qt page. The strategy retains proposal
construction, configured BUY quantity and full-position SELL behavior.

The six selected closes, previous/current averages, raw crossover and position
filter are diagnostic presentation facts. GUI BUY/SELL output is non-authoritative
for D7 and cannot authorize publication or execution. Default desktop composition
still reports unavailable Operations data until a reviewed read-only service is
provided.

Current operator-reported production evidence is D5 READY 6/6 through 2026-09-18
and accepted D7-A for decision `f2188b5e-e6a4-5398-be41-8867d9268355`, intended
execution session 2026-09-21. The namespace is PRESENT_VALID; D7-B is unnecessary.
D7-C remains **protected and unauthorized**. D8-B remains protected and not run.
All eight production effect gates must remain committed false. No production
inspection or effect was performed to create this record.

## Next safe checkpoint

Bounded O1-O4 hygiene and strategy parity review, focused tests, presentation
hardening and integration planning. This acceptance records the supplied O4
checkpoint; it is not full combined-tree certification or approval of a new
production boundary. Findings requiring strategy identity/authority changes
must be escalated before implementation.
