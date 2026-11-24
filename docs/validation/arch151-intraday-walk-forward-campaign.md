# Architecture 151 — Validation plan and evidence boundary

**Status:** synthetic source-foundation tests and local focused checks are defined below. This document does not record source acceptance, integration, or terminal mapped CI. The source checkpoint candidate has not yet completed its push-triggered GitHub FULL certification.

## 1. Scope and safety boundary

The current validation surface covers immutable population identity, deterministic sparse feature contracts, pure completed-bar signal/setup predicates, typed shared execution policy, walk-forward and economic records, qualification, prior-trial accounting, descriptive ranking, zero-or-one freeze, and fail-closed holdout/extension authorization. It is synthetic-only. It does not validate or claim a complete market replay engine.

No accepted-custody file was read; no real strategy replay, provider/credential/Robinhood/broker call, paper/live effect, or production mutation occurred. No 2024+ data was opened. Architecture 150 remains immutable negative evidence and was neither modified nor rerun.

## 2. Synthetic test map

The focused synthetic implementation is `tests/experiments/test_arch151_intraday_walkforward.py`, exercising `src/trading_bot/experiments/arch151_intraday_walkforward.py`.

| Contract | Synthetic proof points |
|---|---|
| Exact closed population, stable identities, immutability, parameter binding | `test_canonical_population_is_exact_ordered_immutable_and_typed`; `test_program_identities_bind_complete_canonical_semantics`; `test_signal_predicates_and_result_types_are_public_api` |
| Sparse 5m/15m aggregation, exact constituents, calendar grid and early closes | `test_sparse_aggregation_omits_incomplete_bucket_and_preserves_complete_bar`; `test_aggregation_rejects_duplicate_unscheduled_and_off_grid_minutes`; `test_sparse_aggregation_respects_published_early_close` |
| Session VWAP from actual eligible one-minute HLC3 × volume, session reset and fail-closed gaps/denominators | `test_session_vwap_uses_observed_minute_hlc3_volume_and_resets_per_session`; `test_session_vwap_drops_missing_bucket_without_synthesis_or_carry`; `test_session_vwap_rejects_zero_observed_volume`; `test_session_vwap_rejects_any_source_session_that_starts_after_open`; `test_one_minute_bar_has_unambiguous_completion_time` |
| Family A complete prior-only calibration, dimensionless noise, price-scaled stop and confirmation/window causality | `test_family_a_entry_window_applies_to_final_confirmation_bar_only`; `test_family_a_rejects_off_grid_and_mismatched_session_observations`; `test_family_a_calibration_is_prior_only_dimensionless_and_frozen`; `test_family_a_uses_price_times_dimensionless_noise_for_stop_risk` |
| Family B distinct breakout → retest → reclaim chronology and reachable predicate | Covered by the Family B parameterized case in `test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates`; includes setup transitions and exact configured chronology |
| Family C normalized deviation, sigma-to-price stop, warmup, efficiency ratio and strict exit chronology | `test_family_c_deviation_is_normalized_and_stop_converts_to_price_distance`; `test_family_c_rejects_insufficient_warmup_and_zero_er_denominator`; `test_family_c_rejects_off_grid_and_cross_session_history`; `test_family_c_exit_rejects_earlier_or_different_session_bar` |
| Family D session EMA/ATR reset, exact timestamp alignment and bar-bound VWAP observations | `test_family_d_ema_atr_and_cross_confirmation_reset_at_gaps`; `test_family_d_vwap_observations_bind_exact_confirming_bars` |
| Predicate reachability for all 16 exact programs on a synthetic regular-session stream | `test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates`; `test_canonical_entry_windows_are_structurally_reachable_from_session_grid` |
| Shared immutable policy, cost cases, stop/target ordering, missing observations, liquidation and no retrospective final-bar rule | `test_causal_execution_policy_and_cost_cases_are_closed_contracts` |
| Exact five expanding folds, all 15 fold/economics records, chronology and identity validation | `test_walk_forward_folds_are_exact_expanding_chronology`; `test_fold_evaluation_batch_is_complete_ordered_and_source_bound`; `test_fold_metrics_reject_nonfinite_or_undefined_economics` |
| Full-session aggregation, summed gross-P&L profit factor and drawdown across concatenated years | `test_development_aggregate_uses_summed_pf_and_chained_drawdown` |
| Each frozen qualification threshold independently rejected; STRESS qualification and diagnostic-only ZERO | `test_development_qualification_rejections_are_independently_testable`; `test_qualification_uses_stress_and_fails_closed_without_dsr`; `test_zero_economics_are_diagnostic_and_never_replace_stress_qualification` |
| Exact prior-trial keys, deduplication, 24 G1 slot IDs, ledger identity and effective count | `test_prior_trial_ledger_is_exact_deduplicated_and_effective_count_is_64` |
| DSR probability threshold contract, no unverified probability authority, all ranking tie-breaks and full-population preservation | `test_selection_probability_threshold_is_diagnostic_and_decimal_only`; `test_ranking_uses_every_frozen_lexicographic_tie_break`; `test_public_synthetic_ranking_preserves_all_canonical_slots` |
| Zero-or-one freeze, no caller-selected identity, holdout/extension denial and deferred DSR producer | `test_final_freeze_requires_full_population_and_remains_zero_until_dsr_exists` |

The predicate reachability fixtures are synthetic completed-bar observations only. They prove that each family’s configured predicate and setup transition can be reached without simulating fills, positions, capital allocation, or realized P&L.

## 3. Source-only checkpoint and mapped certification

The current checkpoint route is `arch151-intraday-walkforward-foundation`, owned by branch `feature/research-arch151-intraday-walkforward-current`. It is registered as a source-only checkpoint with `preflight=None`, `execute=None`, and `remote_head_env=None`; it has no protected-effect dispatch. The active source-gate workflow routes the checkpoint, and the current certification profile maps it to GitHub-owned canonical `full`.

Route and current-authority tests reside in:

- `tests/runtime/checkpoint_runner/test_core.py` — source-only checkpoint registration, route ownership, and no protected execution surface.
- `tests/runtime/checkpoint_runner/test_ci.py` — active source-gate route, push association, FULL profile ownership, and current job-topology/coherence checks.
- `tests/runtime/checkpoint_runner/test_source_authority.py` — current authority projections and preservation of immutable historical security/source pins.

The route is not registered as a historical ACTIVE_CI checkpoint. Current mutable routing/topology tests assert ownership and expected relationships rather than freezing unrelated mutable module inventories. Historical predecessor source pins remain exact and unchanged.

## 4. Focused local verification

The focused selection for this source composition includes the Arch151 module and current runner authority/coherence tests, plus directly affected current consumers:

```powershell
python -m pytest `
  tests/experiments/test_arch151_intraday_walkforward.py `
  tests/runtime/checkpoint_runner/test_core.py `
  tests/runtime/checkpoint_runner/test_ci.py `
  tests/runtime/checkpoint_runner/test_source_authority.py `
  tests/review_paper/test_arch134_readonly_deployment_admission_diagnostic.py `
  tests/experiments/test_research_strategy_production_compatibility.py `
  tests/scripts/certification_runner/test_results.py `
  tests/scripts/certification_runner/test_source.py `
  -p no:cacheprovider --basetemp="F:\AI\temp\pytest\<fresh-guid>" -q
```

Use the repository-approved interpreter resolved to this checkout and a new GUID-based external basetemp for each invocation. The composed local focused selection completed with 644 passing tests. Focused Ruff check, Ruff format check, and source diff checks passed for the implemented source/test composition. These are local prepublication checks, not the mapped canonical FULL result. Do not run local canonical FULL for this mapped checkpoint.

The push-triggered GitHub source-gate and canonical FULL result remain pending. Record the exact pushed source identity, run/attempt, conclusion, and complete required topology only after that run reaches terminal state. A queued or in-progress run is not success; preserve terminal red evidence and do not rerun unchanged CI.

## 5. Evaluator-owned validation still required

The following tests and capabilities are outside the source foundation and remain required before the corresponding later authority can exist:

- Independently reviewed and frozen actual DSR/reviewed-equivalent calculation, with authenticated input/result provenance and the >=0.95 requirement. No production producer currently exists; unverified or synthetic probability cannot qualify.
- Authenticated development evidence issuer, exact candidate binding, and real qualification evidence over all five folds and three economics.
- Read-only custody authority and real strategy replay for the exact frozen candidate; no source-foundation API reads or opens custody.
- Position/fill accounting and replay behavior for next-minute entries, stop gaps, ambiguous stop/target bars, target costs, trailing updates, elapsed holding/cooldown, pending exits, session liquidation, recovery, and complete failure evidence.
- Authenticated holdout PASS issuance and binding, holdout/extension authorization tests against source-owned freeze evidence, and controlled 2024–2025 / Jan–Oct 2026 opening tests. These remain sealed until their respective gates pass.

Synthetic foundation records test pure formulas, threshold boundaries, ordering, and fail-closed rejection. They do not create authenticated evidence, a qualifying candidate, a holdout permission, an extension permission, or authority to access later data.
