# PD2D1 Real-Host P1 Diagnostic — Attempt 1

## Execution identity and source

The reviewed P1 diagnostic ran exactly once under:

```text
principal:     DESKTOP-I4DOKM7\Trading
SID:           S-1-5-21-1397534616-3988210162-180023805-1009
Administrator: False

HEAD:   7931d8944acae8b52f9ba794fe93a80a51376660
TREE:   6c4827216824bb431d71d5fa060be6cfc121c4d8
status: clean
```

## Exact result

```json
{"exception_family":"VALUE_ERROR","reason":"P1_BUILD_BLOCKED","schema":"pd2d1-p1-readonly-diagnostic/v1"}
```

```text
exit: 8
```

## Observed boundary progression

- Preflight passed.
- Genuine C1 passed.
- Genuine P2 passed.
- Genuine B1 entry and reconciliation passed.
- P1 request construction passed.
- P1 build failed.
- B1 released normally.
- No P1 replay occurred.
- No `PaperOperationIntent` was created by this diagnostic.
- No `VerifiedPaperOperationExecutionInputs` was created.
- No Architecture-67 inspection or execution occurred.
- No transition, receipt, provider, or broker action occurred.

```text
PD2D1_REAL_HOST_QUALIFIED = NO
PD2D2_AUTHORIZED          = NO
```

## Reviewed root cause

`PortfolioConstraints` legitimately permits `None` for both
`minimum_position_weight` and `maximum_one_way_rebalance_turnover`. The
canonical checkpointed-request serializer and parser incorrectly assumed that
both fields were always `Decimal` values. In this frozen attempt, the immediate
trigger was `minimum_position_weight=None`, which reached
`canonical_decimal(None)` during P1 checkpointed-request identity construction.

This record does not claim a successful correction. Successful correction
requires source tests and a later, separately reviewed real-host P1
requalification.
