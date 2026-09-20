# PD4 Operator Observability O1-O4 Source Certification

## Status and scope

**ACCEPTED — REPLACEMENT-CERTIFIED SOURCE / PRE-MERGE**

This record closes the source-certification boundary for the forward-integrated
PD4 operator-observability O1-O4 milestone. It is source-only. It authorizes no
production snapshot invocation, provider effect, decision publication,
settlement, recovery, scheduler mutation, broker effect, or live effect.

The historical `feature/pd4-operator-observability` branch remains reference
history only and must not be merged directly into `develop`.

## Certified source identity

```text
integration base HEAD:  f7a177db37d6783d4e9865cc5bb98292f4907274
integration base TREE:  8fe7d9175f5286bf6c88924f5dc3829012b13cd2
source branch:          feature/operator-observability-o1-forward-integration
certified source HEAD:  4c2a064e31d460dd3c7534fadad6c50204ffcd82
certified source TREE:  9d341fcfd6eb5493887012814c5943850d903744
ahead/behind base:      9 / 0
changed files vs base:  28
```

This exact source identity remains authoritative even if a later docs-only
closeout commit advances the feature branch.

## Accepted checkpoint lineage

```text
O1 accepted source:
b836236cc356cf1e530ecc938a6e423c5baf1660

O2 initial review object:
20a96c12b1a65d088da45a3557786aaf0a682703

O2 accepted provenance-lifetime correction:
964c12704ab3cb189cc3674471682e9488bce757

O3 accepted source:
bd6715ff6beb777611a23709c68dde26c8a2f2d1

O4 initial accepted-shape source:
d37efbffbc2e5b435c69120d3e89d6c4eb80349f

O4 fail-closed correction:
a075b1793d36cb1974d6bd46d07e2bc1930bbaeb

post-O4 overview expectation repair:
9e27f05ee51338efa97927f44d83a604e5b20529

A4 test-service observability adaptation:
827f65ca5ad3b382120ad39393a4c982abe34689

A4 formatting correction / final source:
4c2a064e31d460dd3c7534fadad6c50204ffcd82
```

The two post-O4 behavioral test corrections align existing GUI test fixtures
with the accepted O3 service contract. They do not change production/runtime
behavior.

## Accepted functionality

### O1 — bounded observability presentation

O1 provides Qt-free bounded models/adapters for selected-C3 warm-up and effect
gate facts. Presentation objects contain display facts rather than reusable
production authority.

### O2 — read-only production observability snapshot

O2 provides a zero-semantic-argument read-only runtime/CLI/launcher. It derives
current production facts independently and leaves all eight effect gates closed.
The accepted correction retains the selected-C3 provenance lifetime through the
full proof lifetime rather than retaining only the reader object.

### O3 — read-only Operations GUI

O3 adds the Operations page and current navigation/service integration. The
default GUI service remains deterministic unavailable/read-only. GUI startup
does not call the O2 production boundary. The page exposes no mutation/effect
controls and renders service-derived text as literal plain text.

### O4 — deterministic strategy preview

O4 adds a pure diagnostic strategy preview that consumes explicit pure
diagnostic inputs and calls the existing
`MovingAverageCrossoverStrategy.evaluate` implementation exactly once. It
does not duplicate moving-average arithmetic or proposal-ID derivation.

The preview preserves the current Decimal object/representation contract and
current proposal ID, reason, side, and quantity. Ordinary evaluation failures
are sanitized to bounded `BLOCKED`; `BaseException` is not swallowed.

## Certification evidence

Focused source verification before the broad gate:

```text
O1-O4 focused gate:                 122 passed
A4/MainWindow focused regression:    23 passed
```

Final replacement certification:

```text
broad non-Architecture-77:        5,789 passed, 17 skipped
Architecture-77 clean harness:      758 passed
combined:                         6,547 passed, 17 skipped
Ruff check:                       PASS
Ruff format --check:              PASS (564 files already formatted)
git diff --check:                 PASS
git diff --cached --check:        PASS
feature worktree/index:           clean
```

The broad non-Architecture-77 run completed in 525.43 seconds.

The first Architecture-77 run in the feature worktree encountered
`PermissionError [WinError 5]` at the harness's fixed repository-local path:

```text
.pytest_cache/ai-trading-bot-lifecycle-arbiters-v1
```

This is the known legacy Windows cache-path condition. No cache repair,
environment-variable namespace substitution, permission workaround, or source
mutation was used. A clean detached certification worktree pinned to the exact
certified source commit/tree collected 758 Architecture-77 tests and passed all
758 in 1023.94 seconds.

## Safety and authority result

Certification preserves the current authority/effect boundaries:

- all eight committed production effect gates remain false;
- O2 is read-only and does not authorize or perform capture, publication,
  Paper-v2 execution/settlement, recovery, provisioning, scheduling, broker, or
  live effects;
- GUI startup cannot invoke O2 or O4 evaluation;
- default Operations presentation is unavailable and non-authorizing;
- GUI state retains no reusable C1, selected-C3, account, settlement, or
  execution capability;
- O4 retains no `BacktestContext` or domain proposal in the returned view;
- current Decimal and deterministic proposal identity behavior remains
  authoritative;
- no production, Trading-principal, broker, scheduler, provider, settlement, or
  other effectful command ran as part of this source milestone.

An earlier read-only D8-A invocation occurred before the intended settlement
session was completed. It safely returned `NO_SETTLEMENT_PENDING` for completed
session 2026-09-18 with all gates closed and no real effect. It is historical
evidence only and does not authorize or satisfy the later D8-A checkpoint.

## Next checkpoint

The next safe source checkpoint is PR review/integration of
`feature/operator-observability-o1-forward-integration` into current
`develop`. PR creation or metadata mutation and merge remain explicit operator
approval boundaries.

The next protected operational checkpoint remains a fresh zero-semantic-
argument D8-A Trading-principal settlement qualification when the intended
execution session and selected-C3 evidence are eligible. D8-B effectful
settlement remains protected and unauthorized.
