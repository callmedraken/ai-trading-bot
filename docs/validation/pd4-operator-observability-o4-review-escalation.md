# O4 bounded review: Decimal contract escalation

Date: 2026-09-19. Status: **SOL-APPROVED CORRECTION IMPLEMENTED**.

## Resolution

Sol approved a compatibility-first correction that freezes moving-average
arithmetic and the strategy's existing `normalize()`-based desired-quantity
identity rendering to an explicitly constructed strategy-owned Decimal context:
precision 28, `ROUND_HALF_EVEN`, `Emin=-999999`, `Emax=999999`, capitals 1,
clamp 0, with `InvalidOperation`, `DivisionByZero`, and `Overflow` trapped.
Both operations now execute through `localcontext()` and do not consult ambient
Decimal state or mutable `DefaultContext`.

The correction preserves the namespace, proposal identity-material fields and
ordering, normal-context proposal IDs and reasons, crossover/equality behavior,
configured BUY quantity, full-position SELL quantity, and Decimal-subclass
configuration compatibility. Focused strategy regressions pin the historical
golden proposal ID `f596497b-11fd-5213-9ccb-9960a4b10ec1` and O4 MA3/MA5 BUY
vector under normal, low-precision/`ROUND_DOWN`, and high-precision/`ROUND_UP`
ambient contexts. A pure Architecture-94 regression also proves identical plan,
artifact, and checkpointed-request semantics under normal and hostile contexts.
The requested focused strategy, Architecture-94, unattended-decision,
observability, and CLI regression gate passed with 275 tests; Ruff check and
Ruff format verification passed across the 12 relevant Python files.

This source correction does not retroactively change O4 acceptance chronology
or authorize production activity. The accepted D7-A result remains historical
evidence and must be rerun after controlled forward integration of the corrected
source. D7-C remains protected and unauthorized; all eight effect gates remain
false.

## Checkpoint and scope

Starting source HEAD: `2fab48301530a89df21391c047f848eb3fd97272`.
Starting tree: `f8df06396a5203367bb9b0abdbcfd167bfa46d67`.
Phase 1 acceptance documentation was committed as `92fd2be`.
The supplied 266-pass O4 evidence remains historical acceptance evidence.
This follow-up does not certify ambient-context independence.

Phase 2 review began with O1/O4 models, adapters, O2 runtime composition, the
Operations page and service use, O4 strategy diff and existing focused tests.
The review found the Decimal issue below before completing the later phases.
Phases 2-3 are incomplete; Phases 4-8 were not completed. No strategy fix,
new production composition, GUI change, merge or full certification was made.

## Reproduced finding

`src/trading_bot/strategies/moving_average.py` uses ambient Decimal arithmetic
in `_average` and ambient-context `normalize()` in `_canonical_decimal`.
The latter is part of UUID5 proposal identity material.

A pure in-memory reproduction used the existing `make_context` test helper:
closes `10, 10, 9, 12`, windows 2/3, desired quantity `1.23456789`, flat
position. Context construction occurred before changing precision. The same
strategy and context were evaluated under two `decimal.localcontext()` values:

| Precision | Proposal ID | Current long average in reason |
| --- | --- | --- |
| 28 | `f596497b-11fd-5213-9ccb-9960a4b10ec1` | `10.33333333333333333333333333` |
| 6 | `ecf82ed3-2d10-516f-86a4-5ee9eb52bf53` | `10.3333` |

The pre-O4 source loaded from accepted O3 commit `fd504503` produced the same
two respective IDs. This is an inherited problem, not a new O4 identity change.

For the operator-reported six-close sequence
`764.29, 760.88, 757.39, 754.05, 762.6, 761.69`, windows 3/5 and quantity 1:
precision 28 produced current averages `759.4466666666666666666666667` and
`759.322`; precision 4 produced `759.7` and `759.4`. Both runs reported BUY.
No production history or account was read for either reproduction.

The shared evaluator prevents duplicate implementation but does not itself
freeze the Decimal context across independent callers. A precision/rounding
contract requires explicit architectural review. Simply changing normalization
or arithmetic could change proposal IDs, reason bytes and downstream decisions.
The session request explicitly requires stopping before changing production
identity material or working around this boundary. No such change was made.

## Findings not requiring a change in this checkpoint

- The Qt page imports presentation models/formatting, not production runtime.
- Labels use PlainText; tables disable editing and sorting.
- Page state is immutable; existing tests verify navigation reuses one acquired
  snapshot. This is a snapshot display, not an implemented live refresh service.
- O4 uses the source-owned evaluator rather than GUI crossover arithmetic.
- Decimal display formatting uses `format(value, "f")`, not normalization.
- All eight committed production gate assignments are still false.

These are bounded observations, not a completed O1-O4 audit. Source acceptance
and integration readiness must not be conflated.

## Verification performed

Fresh focused run after the documentation checkpoint:

```powershell
$testTemp = 'F:\AI\temp\pytest\o4-review-' + [guid]::NewGuid().ToString('N')
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp=$testTemp tests/strategies/test_moving_average.py tests/gui/test_operator_observability_models.py tests/gui/test_operator_observability_adapters.py tests/gui/test_operator_observability_page_qt.py tests/gui/test_operator_observability_snapshot_adapter.py tests/runtime/test_operator_observability_snapshot.py tests/cli/test_pd4_operator_observability_snapshot.py tests/cli/test_pd4_operator_observability_source_launcher.py
```

Result: **69 passed in 5.66s**. This is a smaller explicit regression selection,
not a rerun of the supplied 266-test acceptance gate. No source/test file changed.
Ruff check passed; Ruff format --check passed (14 relevant source/test files).
No full suite was run. The system Python lacked pytest; verification used the
existing project virtual environment, without installing or changing packages.

## Next recommended milestone: Sol High Decimal contract review

Ready-to-paste review request:

> Review the inherited ambient-Decimal dependency in moving_average.py using
> docs/validation/pd4-operator-observability-o4-review-escalation.md. Decide the
> arithmetic precision/rounding and proposal-ID compatibility contract before
> authorizing any implementation. Compare pre-O4/O4 behavior, including config
> and Decimal subclasses, equality boundaries, reason bytes, quantities and
> position filtering. Preserve all eight false production gates and frozen
> D5/D7/D8-D9 worktrees. No production I/O or effect is authorized. Specify a
> bounded implementation prompt and strategy + Architecture-94/manual-paper +
> G6/D7 read-only focused tests. Reserve the full suite for the final combined
> integration candidate. Then resume the unfinished observability review phases.

Do not treat a normal-context regression pass as resolving this design issue.
Do not run a broad suite now merely to reconfirm this documentation change.
After an approved combined integration tree exists, the default full command is:

```powershell
$testTemp = 'F:\AI\temp\pytest\pd4-integration-' + [guid]::NewGuid().ToString('N')
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp=$testTemp
```

Use the reviewed Architecture-77 Windows split-certification procedure if its
fixed arbiter namespace condition applies; this session did not qualify that
future integration worktree or authorize executing that certification.

## Protected production state

Operator-provided state remains D5 READY 6/6 through 2026-09-18, D7-A accepted,
namespace PRESENT_VALID (D7-B unnecessary), D7-C protected/not run and D8-B
protected/not run. Candidate is `f2188b5e-e6a4-5398-be41-8867d9268355`, intended
execution session 2026-09-21. No scheduler, credentials, production storage,
provider, settlement, recovery, broker or live operation was performed.
