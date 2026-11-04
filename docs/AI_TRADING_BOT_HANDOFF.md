# AI Trading Bot - Current Handoff

## Verified P00 and current source boundary

Independently accepted P6 completed-close source, integrated remote develop:

    HEAD 04e02042f0bd34b2fb7c603b4dfb1b68c23cf57f
    TREE 7269c857f86e2b0bec352ff04ecca9788d571e2f
    feature FULL 41759329337 / attempt 1 / SUCCESS / seven lanes
    develop 41778371132 / attempt 1 / SUCCESS / exact_feature_certification

Independent acceptance and user-run integration were recovered from connected
ChatGPT "Review Workflow Handoff"; remote identities and terminal jobs were
reverified for prototype execution. Codex did not perform integration.

P6 worktree: F:\AI\worktrees\ai-trading-bot-p6-tiny-live-current.
Branch: feature/robinhood-p6-tiny-live-current. P6 intentionally uses one captured
baseline quote response for the typed official close plus one exact 59-session
history request. No synthetic OHLCV, second quote/history call, shifted retry or
fallback is permitted. Failure to obtain the official close stops that path.
All four consumed history-only attempts and diagnostics remain immutable;
[the P6 contract](architecture/147-p6-tiny-live.md) owns their exact records.

## Prototype implementation continuation

Worktree: F:\AI\worktrees\ai-trading-bot-live-prototype-current.
Branch: feature/robinhood-live-prototype-current.
Checkpoint: arch147-live-prototype; GitHub-owned FULL; no preflight/execute.
Preserved rejected prototype publication:

    HEAD 01adf7f0808970576b263f158d2dd121b216d733
    TREE bd0fb74dacbd22aa832d991c0876fd14ad478789
    GitHub 41788777182 / attempt 1 / terminal FAILURE

Source-static and active tests passed; six FULL lanes passed. Broad-3 failed two
current `test_core.py` registry/topology expectations, reproduced on unchanged
source. Admission omitted that module: `PREPUBLICATION_COVERAGE_DEFECT`. The red
run/commit are never rerun or rewritten. A separately authorized bounded current
runner/admission/test correction requires new certification and independent review;
no prototype logic or effect changes.
Require the new clean-candidate admission's `executed_tests` to contain
`tests/runtime/checkpoint_runner/test_core.py` before its one ordinary push.
Do not infer acceptance, integration or provider readiness from CI alone.

The [prototype contract](architecture/147-live-prototype-current.md) owns the
frozen interfaces, exact formulas/selection, lifecycle/effect ceiling and launcher.
The [ledger](validation/arch147-live-prototype.md) owns task status and acceptance
rows. Luna owns disjoint research/widget files; Sol owns shared composition,
registry/workflow/coordination docs and publication. All outputs are on F:.

Explicit synthetic launch uses scripts/run_live_prototype.py --synthetic
--state-root <fresh F:\AI\temp subdirectory>. Optional --comparison-report
<absolute report path> loads bounded evidence on a worker. Help is effect-free.
Synthetic construction/navigation cannot connect, arm or trade. Start only starts
a fake worker; Stop/Close confirm all workers terminated, without cancellation
or liquidation. Research artifact opening leaves the active binding unchanged.
Real broker controls remain outside the GUI and fail closed here.

## Next milestone and stop conditions

Complete the bounded registry/admission correction, one new clean admission and
terminal mapped FULL, then independent review. No further prototype delegation
precedes that result/review. Only afterward continue toward native UAT and separately
reviewed current-data, binding
parity and complete owned entry/exit/recovery. No paper soak. Do not run a real
campaign until its existing dataset identity is independently admitted. No new
variants, provider acquisition or FINAL_HOLDOUT access to manufacture a result.

Protected official-close preflight remains a separate reviewed operator step
on the exact accepted integrated P6 source, place=cancel=0. No fifth history-only
attempt. No live order is authorized by the prototype task. Live readiness is
blocked until exact input-basis, fractional owned exit, durable cumulative budgets
and restart/reconciliation requirements have independent accepted evidence.
Never reset consumed markers or repair ambiguous state through retry.
