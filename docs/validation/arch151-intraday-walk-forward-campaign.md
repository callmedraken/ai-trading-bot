# Architecture 151 — Validation plan and evidence boundary

**Status:** this document records synthetic source-foundation and offline-evaluator coverage, focused local evidence, and the remaining holdout/extension authority boundary. It does not assert source acceptance, integration, or any mapped CI status or outcome.

## 1. Scope and safety boundary

The current validation surface covers immutable population identity, deterministic sparse feature contracts, pure completed-bar signal/setup predicates, the chronological one-minute evaluator, exact 480-record development composition, DSR calculation, source-bound report serialization, qualification, prior-trial accounting, descriptive ranking, zero-or-one freeze, and fail-closed holdout/extension authorization. Evaluator tests use only sealed synthetic history; they do not exercise the accepted Arch150 custody loader.

No accepted-custody file was read; no real-data strategy replay, provider/credential/Robinhood/broker call, paper/live effect, or production mutation occurred. No 2024+ data was opened. The implemented evaluator is source-bound to reuse accepted Arch150 sparse SPY/QQQ one-minute custody for 2016–2023 without development reacquisition, but its accepted-source entry point was not invoked. Architecture 150 remains immutable negative evidence and was neither modified nor rerun.

## 2. Synthetic test map

The focused synthetic implementation is `tests/experiments/test_arch151_intraday_walkforward.py`, exercising `src/trading_bot/experiments/arch151_intraday_walkforward.py`.

| Contract | Synthetic proof points |
|---|---|
| Exact closed population, stable identities, immutability, parameter binding | `test_canonical_population_is_exact_ordered_immutable_and_typed`; `test_program_identities_bind_complete_canonical_semantics`; `test_signal_predicates_and_result_types_are_public_api` |
| Sparse 5m/15m aggregation, exact constituents, calendar grid and early closes | `test_sparse_aggregation_omits_incomplete_bucket_and_preserves_complete_bar`; `test_aggregation_rejects_duplicate_unscheduled_and_off_grid_minutes`; `test_sparse_aggregation_respects_published_early_close` |
| Arch150 sparse 5-minute aggregation semantic parity on an early close with missing buckets | `test_five_minute_sparse_aggregation_matches_arch150_on_early_close_gaps` |
| Session VWAP from actual eligible one-minute HLC3 × volume, session reset, and source-bound verified post-open sparse input | `test_session_vwap_uses_observed_minute_hlc3_volume_and_resets_per_session`; `test_session_vwap_drops_missing_bucket_without_synthesis_or_carry`; `test_session_vwap_rejects_zero_observed_volume`; `test_session_vwap_requires_exact_evidence_for_post_open_projection`; `test_one_minute_bar_has_unambiguous_completion_time` |
| Family C/D missing-opening recovery only through sealed evaluator-owned sparse-session evidence; arbitrary caller streams and Boolean/fake-auth evidence rejected | `test_family_c_restarts_from_verified_sparse_projection_after_missing_open`; `test_family_c_requires_sealed_sparse_session_and_valid_frozen_sigma`; `test_family_d_gap_recovery_requires_fresh_warmup_and_verified_projection`; `test_sparse_session_evidence_has_no_public_boolean_or_constructor_issuer` |
| Family A symbol-bound calibration, full historical-session completeness, causal opening-window eligibility, source-digest binding, dimensionless noise and price-scaled stop | `test_family_a_calibrations_are_independent_and_bound_to_symbol`; `test_family_a_calibration_rejects_mixed_symbol_history`; `test_family_a_rejects_both_calibration_to_current_symbol_mismatches`; `test_family_a_rejects_confirmation_symbol_mismatch`; `test_family_a_historical_measure_requires_every_scheduled_session_minute`; `test_family_a_historical_measure_uses_published_early_close_length`; `test_family_a_current_opening_measure_is_causal_without_future_bars`; `test_family_a_calibration_is_prior_only_dimensionless_and_frozen`; `test_family_a_uses_price_times_dimensionless_noise_for_stop_risk`; `test_family_a_entry_window_applies_to_final_confirmation_bar_only`; `test_family_a_rejects_off_grid_and_mismatched_session_observations` |
| Family B complete open-anchored opening range and symbol-bound signal, distinct breakout → retest → reclaim chronology, bounded deadline, failed-sequence and post-gap fresh-setup recovery, and completion-timestamp binding | `test_family_b_recovers_with_a_fresh_setup_after_failure`; `test_family_b_recovers_after_a_missing_post_opening_bucket`; `test_family_b_missing_or_incomplete_opening_range_fails_closed`; `test_family_b_retest_deadline_includes_exact_final_subsequent_bar`; `test_family_b_signal_is_bound_to_current_reclaim_completion`; `test_family_b_signal_binds_execution_symbol`; Family B cases in `test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates` |
| Family C normalized deviation, sigma-to-price stop, warmup, efficiency ratio, exact entry identity, same-instrument exit, strict session/resolution/chronology, and frozen sigma validity | `test_family_c_deviation_is_normalized_and_stop_converts_to_price_distance`; `test_family_c_rejects_insufficient_warmup_and_zero_er_denominator`; `test_family_c_rejects_off_grid_and_cross_session_history`; `test_family_c_exit_rejects_earlier_or_different_session_bar`; `test_family_c_entry_and_exit_are_bound_to_the_same_instrument`; `test_family_c_requires_sealed_sparse_session_and_valid_frozen_sigma` |
| Family D per-symbol SMA-seeded EMA reseed, fresh post-gap setup/ATR warmup, exact aligned overlap, no stale or cross-gap confirmation, and bar-bound VWAP observations | `test_family_d_ema_atr_and_cross_confirmation_reset_at_gaps`; `test_family_d_vwap_observations_bind_exact_confirming_bars`; `test_family_d_reseeds_and_finds_fresh_signal_after_either_symbol_gap`; `test_family_d_does_not_bridge_cross_confirmation_across_a_gap`; `test_family_d_gap_near_close_without_fresh_warmup_has_no_signal` |
| Family D current-decision-only signal lifecycle, fresh later setup, expired entry not suppressing a later opportunity, warmup after gaps, deterministic same-bar tie-break, and prefix consistency | `test_family_d_emits_first_valid_signal_only_at_current_decision_bar`; `test_family_d_later_independent_setup_signals_after_first_decision`; `test_family_d_expired_first_entry_does_not_block_later_signal`; `test_family_d_gap_recovery_requires_fresh_warmup_and_verified_projection`; `test_family_d_same_bar_signal_tie_break_is_stable`; `test_family_d_each_prefix_matches_its_current_decision_result` |
| Predicate reachability for all 16 exact programs on a synthetic regular-session stream | `test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates`; `test_canonical_entry_windows_are_structurally_reachable_from_session_grid` |
| Shared immutable policy, cost cases, stop/target ordering, missing observations, liquidation and no retrospective final-bar rule | `test_causal_execution_policy_and_cost_cases_are_closed_contracts` |
| Exact five expanding folds, all 15 fold/economics records, chronology and identity validation; v2 evaluation schema/namespace and deterministic downstream identity; invalid integrity evidence fails before economic qualification while valid undefined PF receives an ordinary typed rejection | `test_walk_forward_folds_are_exact_expanding_chronology`; `test_fold_evaluation_batch_is_complete_ordered_and_source_bound`; `test_fold_evaluation_identity_uses_v2_schema_and_namespace`; `test_fold_metrics_reject_invalid_and_preserve_zero_trade_undefined_pf`; `test_invalid_fold_evidence_fails_before_undefined_pf_qualification` |
| Full-session aggregation, finite/+infinity/undefined PF states, zero-trade preservation, zero-gross completed-trade retention, summed gross-P&L PF and drawdown across concatenated years | `test_profit_factor_preserves_zero_trade_win_loss_and_mixed_states`; `test_undefined_and_positive_infinity_aggregate_pf_are_explicit`; `test_profit_factor_ranking_orders_infinity_finite_and_undefined`; `test_development_aggregate_uses_summed_pf_and_chained_drawdown` |
| Each frozen qualification threshold independently rejected; STRESS qualification and diagnostic-only ZERO | `test_development_qualification_rejections_are_independently_testable`; `test_qualification_uses_stress_and_fails_closed_without_dsr`; `test_zero_economics_are_diagnostic_and_never_replace_stress_qualification` |
| Exact prior-trial keys, deduplication, 24 G1 slot IDs, ledger identity and effective count | `test_prior_trial_ledger_is_exact_deduplicated_and_effective_count_is_64` |
| DSR probability threshold contract, no unverified probability authority, all ranking tie-breaks and full-population preservation | `test_selection_probability_threshold_is_diagnostic_and_decimal_only`; `test_ranking_uses_every_frozen_lexicographic_tie_break`; `test_public_synthetic_ranking_preserves_all_canonical_slots` |
| Zero-or-one freeze, no caller-selected identity, holdout/extension denial and degenerate DSR failure | `test_final_freeze_requires_full_population_and_fails_closed_on_degenerate_dsr` |
| Chronological per-slot replay, next-open entry/expiry, typed lifecycle counts, priority ordering, stops/targets/trailing, costs/cash reconciliation, normal/early-close liquidation, failure evidence, and canonical family/resolution/symbol coverage | `tests/experiments/test_arch151_intraday_walkforward_evaluator.py`: `test_b_simulator_fills_next_open_then_target_open_with_cost_reconciliation`; `test_b_simulator_expires_an_absent_next_open_without_chasing`; `test_generated_signal_is_blocked_with_reconciled_terminal_diagnostics`; `test_signal_inside_window_is_blocked_when_scheduled_open_is_after_cutoff`; `test_entry_minute_ambiguous_stop_and_target_resolves_to_stop`; `test_existing_position_exit_priority_uses_stop_gap_then_stop_touch`; `test_target_open_precedes_pending_maximum_hold_at_the_same_open`; `test_elapsed_maximum_hold_exit_remains_pending_across_missing_minutes`; `test_mandatory_liquidation_uses_published_normal_or_early_close`; `test_missing_mandatory_liquidation_fails_with_position_evidence`; `test_each_cost_case_applies_adverse_cost_once_per_actual_fill`; `test_all_canonical_signals_enter_and_exit_through_unmocked_predicates`; `test_canonical_year_batch_keeps_all_slots_costs_and_full_session_denominators` |
| Exact five-year composition, all 480 canonical records, source-kind separation, deterministic canonical report bytes, and report/run/batch constructor rejection | `test_development_composition_preserves_all_480_fold_slot_cost_records`; `test_source_owned_report_binds_all_records_provenance_dsr_and_freeze`; `test_unissued_development_batch_run_and_report_constructors_fail_closed` |

Foundation predicate reachability fixtures use synthetic completed bars. Evaluator fixtures then drive the accepted family predicates through the chronological synthetic one-minute loop, simulated fills, per-slot capital accounting, session returns, and report composition. No test opens accepted custody or executes a real-data replay.

Canonical year-batch and development-run identities are versioned v2 to bind the sealed source-binding identity and complete replay-output digests; the report uses `arch151-development-evaluation-report/v1`, hashes its canonical JSON bytes, and includes all 480 fold records plus all 480 slot-year replay summaries/digests. No real evaluation batch, run, or report existed to remap. Synthetic source binding is labeled `SYNTHETIC_TEST_ONLY` and cannot be used as accepted Arch150 custody evidence.

## 3. Source-only checkpoint and mapped certification

The established source-foundation checkpoint remains `arch151-intraday-walkforward-foundation` on branch `feature/research-arch151-intraday-walkforward-current`, preserving its prior route and certification evidence. The E1 successor is the distinct source-only checkpoint `arch151-intraday-walkforward-evaluator` on the same branch. Changed-path routing selects the evaluator when its source/test or Arch151 design/validation docs are present, including mixed runner/workflow/docs changes; a no-diff route lookup keeps the foundation default. Both specs use `preflight=None`, `execute=None`, and `remote_head_env=None`, have no protected-effect dispatch, and map to GitHub-owned canonical `full`. Neither is registered in the historical `ACTIVE_CI_CHECKPOINTS` tuple.

Route and current-authority tests reside in:

- `tests/runtime/checkpoint_runner/test_core.py` — source-only checkpoint registration, route ownership, and no protected execution surface.
- `tests/runtime/checkpoint_runner/test_ci.py` — active source-gate route, push association, FULL profile ownership, and current job-topology/coherence checks.
- `tests/runtime/checkpoint_runner/test_source_authority.py` — current authority projections and preservation of immutable historical security/source pins.

The evaluator route also owns `tests/experiments/test_arch151_intraday_walkforward_evaluator.py`; the foundation and evaluator both retain the focused foundation module and current runner authority tests. Current route tests exercise default foundation selection, foundation-only changed paths, evaluator-source selection, mixed evaluator/foundation/runner/workflow/docs paths, and pull-request rejection. Historical predecessor source pins remain exact and unchanged.

Neither current route is registered as a historical ACTIVE_CI checkpoint. Current mutable routing/topology tests assert ownership and expected relationships rather than freezing unrelated mutable module inventories.

## 4. Focused local verification

The focused selection for this source composition includes the Arch151 module and current runner authority/coherence tests, plus directly affected current consumers:

```powershell
$python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
$pytestBase = Join-Path 'F:\AI\temp\pytest' ('arch151-e1-' + [guid]::NewGuid().ToString('N'))
& $python -m pytest `
  tests/experiments/test_arch151_intraday_walkforward.py `
  tests/experiments/test_arch151_intraday_walkforward_evaluator.py `
  tests/runtime/checkpoint_runner/test_core.py `
  tests/runtime/checkpoint_runner/test_ci.py `
  tests/runtime/checkpoint_runner/test_source_authority.py `
  tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic.py `
  tests/experiments/test_research_strategy_production_compatibility.py `
  tests/scripts/certification_runner/test_results.py `
  tests/scripts/certification_runner/test_source.py `
  -p no:cacheprovider "--basetemp=$pytestBase" -q
$pytestExit = $LASTEXITCODE
if ($pytestExit -ne 0) { throw "Focused pytest failed with native exit $pytestExit" }
```

Use the repository-approved interpreter resolved to this checkout and a new GUID-based external basetemp for each invocation. The predecessor composed focused selection recorded 973 passing tests; this is predecessor evidence, not the final composed result. The C1 source-foundation focused run recorded 59 passing tests. The initial C2 focused Arch151 module run recorded 76 passed using basetemp `F:\AI\temp\pytest\arch151-c2-final-b5d498ed6fe74e5ba35dc1e74b14946f`; after the fold-evaluation v2 identity correction and exact C1 legacy-ID reconstruction, 77 passed using fresh basetemp `F:\AI\temp\pytest\arch151-c2-v2-legacy-dd96dfc5705f4cb28068e37df72afae1`. Ruff 0.17.3 check, Ruff format check, and `git diff --check` passed after the correction. This document does not record the final composed focused count; consult checkpoint verification evidence for that result. These are local prepublication checks, not a statement about the mapped canonical FULL result. Do not run local canonical FULL for this mapped checkpoint.

The route and GitHub-owned canonical FULL profile are specified in §3. This validation plan records no mapped run identifier, current status, or conclusion.

## 5. Remaining holdout and extension authority boundary

The offline development evaluator and canonical result report are implemented, but this implementation pass performed no accepted-custody read or real-data evaluation. The following capabilities remain unavailable and must be independently reviewed, implemented, and authorized before either sealed later period can be opened:

- A separately authorized invocation of the fixed Arch150 D1R source adapter and evaluator for development-visible 2016–2023 only, followed by independent review of the exact canonical report, all 480 records, source binding, DSR evidence/status, and freeze. The accepted source path was not opened during these synthetic checks.
- A source-owned authenticated development-evidence issuer bound to the exact source-owned freeze and full evidence, if required to enable later holdout authorization. The current `AuthenticatedDevelopmentEvidence` constructor remains unavailable; a report by itself does not open holdout.
- Authenticated holdout permission/result issuance and a reader bound to the exact single frozen candidate. Holdout STRESS must show combined 2024–2025 net return >0, each year >0, combined PF >1.10, drawdown <=15%, active-session fraction >=30%, average completed round trips/year >=80, and no month >40% of total positive P&L. No strategy mutation is allowed after holdout visibility.
- Authenticated same-candidate Jan–Oct 2026 extension authorization and reader after authenticated holdout PASS. Extension STRESS must show net return >0, PF >1.05, drawdown <=15%, at least 6/10 complete positive months, and active-session fraction >=30%. `ARCH151_INTRADAY_RESEARCH_SURVIVOR` permits only a separately authorized paper/shadow translation study; the classification grants no runtime, order, Robinhood, or live authority.

Synthetic source and evaluator records test pure formulas, threshold boundaries, replay ordering, result serialization, and fail-closed rejection. They do not create accepted-custody evidence, a real-data qualifying candidate, holdout or extension permission, or authority to access later data. No mapped CI result is recorded by this validation document.
