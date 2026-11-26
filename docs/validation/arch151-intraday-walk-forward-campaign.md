# Architecture 151 — Validation plan and evidence boundary

**Status:** this document records the accepted E2 source correction, both consumed observations, E3's source-only numerical-reliability correction and terminal mapped FULL timing failure, and the E3-C1 test-fixture timing correction. Review the exact E3-C1 commit and mapped result before any source acceptance or integration.

## 1. Scope and safety boundary

The current validation surface covers immutable population identity, deterministic sparse feature contracts, pure completed-bar signal/setup predicates, the chronological one-minute evaluator, exact 480-record development composition, DSR calculation, report-only annual/campaign economics diagnostics, source-bound passive SPY adjusted-price benchmarks, source-bound report serialization, qualification, prior-trial accounting, descriptive ranking, zero-or-one freeze, fail-closed holdout/extension authorization, and the complete-development custody adapter contract. E2 verified accepted source loading and source-history construction but failed before producing a completed annual artifact. E3 uses only deterministic synthetic fixtures to exercise finite-precision risk validation, annual replay coverage, canonical evidence serialization, and sanitized failure attribution.

During E3, no accepted-custody content was read and no real-data strategy replay, provider/credential/Robinhood/broker call, paper/live effect, or production mutation occurred. Only hashes and lengths of the two already-consumed observation roots were reverified. No 2024+ data was opened. Architecture 150 remains immutable and was neither modified nor rerun.

## 2. Synthetic test map

The focused synthetic implementation is `tests/experiments/test_arch151_intraday_walkforward.py`, exercising `src/trading_bot/experiments/arch151_intraday_walkforward.py`.

| Contract | Synthetic proof points |
|---|---|
| Exact closed population, stable identities, immutability, parameter binding | `test_canonical_population_is_exact_ordered_immutable_and_typed`; `test_program_identities_bind_complete_canonical_semantics`; `test_signal_predicates_and_result_types_are_public_api` |
| Sparse 5m/15m aggregation, exact constituents, calendar grid and early closes | `test_sparse_aggregation_omits_incomplete_bucket_and_preserves_complete_bar`; `test_aggregation_rejects_duplicate_unscheduled_and_off_grid_minutes`; `test_sparse_aggregation_respects_published_early_close` |
| Arch150 sparse 5-minute aggregation semantic parity on an early close with missing buckets | `test_five_minute_sparse_aggregation_matches_arch150_on_early_close_gaps` |
| Session VWAP from actual eligible one-minute HLC3 × volume, session reset, and source-bound verified post-open sparse input | `test_session_vwap_uses_observed_minute_hlc3_volume_and_resets_per_session`; `test_session_vwap_drops_missing_bucket_without_synthesis_or_carry`; `test_session_vwap_rejects_zero_observed_volume`; `test_session_vwap_requires_exact_evidence_for_post_open_projection`; `test_one_minute_bar_has_unambiguous_completion_time` |
| Family C/D missing-opening recovery only through sealed evaluator-owned sparse-session evidence; arbitrary caller streams and Boolean/fake-auth evidence rejected | `test_family_c_restarts_from_verified_sparse_projection_after_missing_open`; `test_family_c_requires_sealed_sparse_session_and_valid_frozen_sigma`; `test_family_d_gap_recovery_requires_fresh_warmup_and_verified_projection`; `test_sparse_session_evidence_has_no_public_boolean_or_constructor_issuer` |
| Family A symbol-bound calibration, full historical-session completeness, causal opening-window eligibility, source-digest binding, dimensionless noise and price-scaled stop | `test_family_a_calibrations_are_independent_and_bound_to_symbol`; `test_family_a_calibration_rejects_mixed_symbol_history`; `test_family_a_rejects_both_calibration_to_current_symbol_mismatches`; `test_family_a_rejects_confirmation_symbol_mismatch`; `test_family_a_historical_measure_requires_every_scheduled_session_minute`; `test_family_a_historical_measure_uses_published_early_close_length`; `test_family_a_current_opening_measure_is_causal_without_future_bars`; `test_family_a_calibration_is_prior_only_dimensionless_and_frozen`; `test_family_a_uses_price_times_dimensionless_noise_for_stop_risk`; `test_family_a_fractional_fill_risk_is_exact_under_ambient_contexts`; `test_family_a_entry_window_applies_to_final_confirmation_bar_only`; `test_family_a_rejects_off_grid_and_mismatched_session_observations` |
| Family B complete open-anchored opening range and symbol-bound signal, distinct breakout → retest → reclaim chronology, bounded deadline, failed-sequence and post-gap fresh-setup recovery, and completion-timestamp binding | `test_family_b_recovers_with_a_fresh_setup_after_failure`; `test_family_b_recovers_after_a_missing_post_opening_bucket`; `test_family_b_missing_or_incomplete_opening_range_fails_closed`; `test_family_b_retest_deadline_includes_exact_final_subsequent_bar`; `test_family_b_signal_is_bound_to_current_reclaim_completion`; `test_family_b_signal_binds_execution_symbol`; Family B cases in `test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates` |
| Family C normalized deviation, sigma-to-price stop, warmup, efficiency ratio, exact entry identity, same-instrument exit, strict session/resolution/chronology, and frozen sigma validity | `test_family_c_deviation_is_normalized_and_stop_converts_to_price_distance`; `test_family_c_rejects_insufficient_warmup_and_zero_er_denominator`; `test_family_c_rejects_off_grid_and_cross_session_history`; `test_family_c_exit_rejects_earlier_or_different_session_bar`; `test_family_c_entry_and_exit_are_bound_to_the_same_instrument`; `test_family_c_requires_sealed_sparse_session_and_valid_frozen_sigma` |
| Family D per-symbol SMA-seeded EMA reseed, fresh post-gap setup/ATR warmup, exact aligned overlap, no stale or cross-gap confirmation, and bar-bound VWAP observations | `test_family_d_ema_atr_and_cross_confirmation_reset_at_gaps`; `test_family_d_vwap_observations_bind_exact_confirming_bars`; `test_family_d_reseeds_and_finds_fresh_signal_after_either_symbol_gap`; `test_family_d_does_not_bridge_cross_confirmation_across_a_gap`; `test_family_d_gap_near_close_without_fresh_warmup_has_no_signal` |
| Family D current-decision-only signal lifecycle, fresh later setup, expired entry not suppressing a later opportunity, warmup after gaps, deterministic same-bar tie-break, and prefix consistency | `test_family_d_emits_first_valid_signal_only_at_current_decision_bar`; `test_family_d_later_independent_setup_signals_after_first_decision`; `test_family_d_expired_first_entry_does_not_block_later_signal`; `test_family_d_gap_recovery_requires_fresh_warmup_and_verified_projection`; `test_family_d_same_bar_signal_tie_break_is_stable`; `test_family_d_each_prefix_matches_its_current_decision_result` |
| Predicate reachability for all 16 exact programs on a synthetic regular-session stream | `test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates`; `test_canonical_entry_windows_are_structurally_reachable_from_session_grid` |
| Shared immutable policy, cost cases, stop/target ordering, missing observations, liquidation and no retrospective final-bar rule | `test_causal_execution_policy_and_cost_cases_are_closed_contracts` |
| Exact five expanding folds, all 15 fold/economics records, chronology and identity validation; fold-evaluation and qualification v3 schemas/namespaces with predecessor schema references; invalid integrity evidence fails before economic qualification while valid undefined PF receives an ordinary typed rejection | `test_walk_forward_folds_are_exact_expanding_chronology`; `test_fold_evaluation_batch_is_complete_ordered_and_source_bound`; `test_fold_evaluation_identity_uses_v3_schema_and_namespace`; `test_qualification_identity_uses_v3_and_preserves_v2_predecessor_schema`; `test_fold_metrics_reject_invalid_and_preserve_zero_trade_undefined_pf`; `test_invalid_fold_evidence_fails_before_undefined_pf_qualification` |
| Full-session aggregation, realized-net and descriptive pre-cost PF states, zero-trade preservation, zero-gross completed-trade retention, summed PF totals across folds and drawdown across concatenated years | `test_profit_factor_preserves_zero_trade_win_loss_and_mixed_states`; `test_undefined_and_positive_infinity_aggregate_pf_are_explicit`; `test_cost_case_pf_uses_realized_net_totals_for_annual_and_aggregate_gates`; `test_profit_factor_ranking_orders_infinity_finite_and_undefined`; `test_ranking_uses_stress_realized_net_pf_not_pre_cost_pf`; `test_development_aggregate_uses_summed_pf_and_chained_drawdown` |
| Each frozen qualification threshold independently rejected; STRESS qualification and diagnostic-only ZERO | `test_development_qualification_rejections_are_independently_testable`; `test_qualification_uses_stress_and_fails_closed_without_dsr`; `test_zero_economics_are_diagnostic_and_never_replace_stress_qualification` |
| Exact prior-trial keys, deduplication, 24 G1 slot IDs, ledger identity and effective count | `test_prior_trial_ledger_is_exact_deduplicated_and_effective_count_is_64` |
| Bailey–López de Prado Eq. 1/2 numerical reference, all-32 trial diagnostics, exact affected slot IDs, fixed effective N=64, and a separate non-authorizing descriptive economic order when DSR is unavailable | `test_bailey_lopez_de_prado_paper_example_matches_eq1_and_eq2`; `test_dsr_unavailable_keeps_all_slots_and_never_drops_undefined_trial`; `test_dsr_invalid_moments_and_degenerate_formula_fail_closed`; `test_dsr_mixed_inactive_and_invalid_candidates_preserve_all_slots`; `test_zero_dispersion_marks_all_32_slots_unavailable_and_preserves_order`; `test_dsr_reference_values_and_complete_population_freeze_are_deterministic` |
| DSR probability threshold contract, no unverified probability authority, all ranking tie-breaks and full-population preservation | `test_selection_probability_threshold_is_diagnostic_and_decimal_only`; `test_ranking_uses_every_frozen_lexicographic_tie_break`; `test_public_synthetic_ranking_preserves_all_canonical_slots` |
| Zero-or-one freeze distinguishes statistical unavailability from a valid campaign with no economic survivor; no caller-selected identity or holdout/extension authority | `test_final_freeze_requires_full_population_and_fails_closed_on_degenerate_dsr`; `test_valid_dsr_with_no_economic_survivor_is_not_statistical_unavailability` |
| Chronological per-slot replay, next-open entry/expiry, typed lifecycle counts, priority ordering, stops/targets/trailing, costs/cash reconciliation, normal/early-close liquidation, failure evidence, realized-net PF after adverse costs, descriptive pre-cost PF, and canonical family/resolution/symbol coverage | `tests/experiments/test_arch151_intraday_walkforward_evaluator.py`: `test_b_simulator_fills_next_open_then_target_open_with_cost_reconciliation`; `test_b_simulator_expires_an_absent_next_open_without_chasing`; `test_generated_signal_is_blocked_with_reconciled_terminal_diagnostics`; `test_signal_inside_window_is_blocked_when_scheduled_open_is_after_cutoff`; `test_entry_minute_ambiguous_stop_and_target_resolves_to_stop`; `test_existing_position_exit_priority_uses_stop_gap_then_stop_touch`; `test_target_open_precedes_pending_maximum_hold_at_the_same_open`; `test_elapsed_maximum_hold_exit_remains_pending_across_missing_minutes`; `test_mandatory_liquidation_uses_published_normal_or_early_close`; `test_missing_mandatory_liquidation_fails_with_position_evidence`; `test_each_cost_case_applies_adverse_cost_once_per_actual_fill`; `test_stress_pf_uses_net_winning_and_losing_trade_outcomes`; `test_all_canonical_signals_enter_and_exit_through_unmocked_predicates`; `test_canonical_year_batch_keeps_all_slots_costs_and_full_session_denominators` |
| Exact five-year composition, all 480 canonical records, source-kind separation, deterministic report bytes carrying all 32 DSR diagnostics and descriptive order, year-batch v3/run v4/report v3 identities with predecessor schemas preserved, and report/run/batch constructor rejection | `test_development_composition_preserves_all_480_fold_slot_cost_records`; `test_source_owned_report_binds_all_records_provenance_dsr_and_freeze`; `test_canonical_year_batch_keeps_all_slots_costs_and_full_session_denominators`; `test_unissued_development_batch_run_and_report_constructors_fail_closed` |
| Bounded reuse equivalence and generated five-year synthetic workload with all 480 non-idle replay records | `test_family_d_program_pair_cache_matches_independent_reference`; `test_family_a_calibration_cache_matches_per_program_reference`; `test_generated_five_year_simulation_composes_non_idle_480_records` |
| Report-only ZERO/BASE/STRESS gross/net trade economics, adverse-cost reconciliation and path comparison, expectancy/win/payoff, full-calendar monthly returns/breadth, holding/time-in-market, exit P&L, signal rejection/expiry diagnostics, conservative observed-minute MFE/MAE, and all-slot/cost retention | `test_economic_diagnostics_reconcile_costs_months_time_and_excursions`; `test_economic_diagnostic_negates_fractional_losses_exactly`; `test_economic_diagnostics_retain_expired_and_blocked_signal_counts`; `test_b_simulator_fills_next_open_then_target_open_with_cost_reconciliation`; `test_entry_minute_ambiguous_stop_and_target_resolves_to_stop`; `test_source_owned_report_binds_all_records_provenance_dsr_and_freeze` |
| Passive SPY annual and aggregate adjusted-price benchmark, exact source price-basis binding, and typed unavailable endpoint preservation without zero-fill or candidate dropout | `test_passive_spy_benchmark_binds_exact_adjusted_price_endpoints`; `test_passive_spy_benchmark_missing_endpoints_are_unavailable_not_zero`; `test_unavailable_annual_benchmark_is_retained_without_zero_fill_or_dropout`; `test_source_owned_report_binds_all_records_provenance_dsr_and_freeze` |
| Full 2016–2023 custody adaptation, synthetic-only boundary substitution, old-stage incompatibility reproduction, exact input digest, SPY/QQQ projections, source-bound features, bounded B5 slot replay, and sanitized projection failure classification | `tests/experiments/test_arch151_intraday_walkforward_evaluator.py::test_arch150_full_input_adapter_preserves_development_history_and_replays`; `test_arch150_adapter_rejects_invalid_population_before_custody_scan`; `test_arch150_adapter_rejects_truncated_population_at_custody_boundary`; `test_arch150_adapter_rejects_mismatched_authority_and_projection_source`; `test_arch150_adapter_sanitizes_projection_construction_failure`; `tests/experiments/test_arch151_intraday_walkforward.py::test_d1r_adapter_is_fixed_and_reuses_arch150_acceptance_without_reading_files` |
| Nearest-rank diagnostic quartiles; source/invocation binding and exact run/report receipt; sealed candidate evidence handoff without holdout authorization; durable create-once artifacts, replay-failure preservation, incomplete classification, sanitized source-load reasons, preserved E1 binding, permanently retired E1/E2 public routes, and annual failure attribution | `tests/experiments/test_arch151_intraday_walkforward_evaluator.py::test_diagnostic_quartiles_use_nearest_rank_without_interpolation`; `tests/experiments/test_arch151_intraday_walkforward_evaluator.py::test_operator_attestation_binds_exact_run_report_and_captured_revision`; `tests/experiments/test_arch151_intraday_walkforward_evaluator.py::test_annual_replay_failure_has_slot_and_operation_context`; `tests/experiments/test_arch151_intraday_walkforward_operator.py::test_operator_persists_exact_report_and_binds_source_and_invocation_once`; `test_source_attestation_issuer_rejects_bare_ids_and_operator_outcomes`; `test_replay_integrity_failure_is_separate_and_never_becomes_report_or_idle`; `test_incomplete_batch_is_retained_without_zero_filling_or_later_years`; `test_source_preflight_failure_is_durable_without_source_or_evaluation`; `test_source_failure_is_sanitized_and_attempt_is_terminal`; `test_source_load_reason_is_typed_and_durable_without_exception_content`; `test_annual_simulation_failure_attribution_is_structured_and_sanitized`; `test_annual_wrapper_does_not_change_existing_chained_failure_classification`; `test_consumed_e1_artifacts_keep_their_exact_historical_binding`; `test_consumed_e2_public_routes_fail_closed_when_root_is_missing`; `test_consumed_e2_public_routes_fail_closed_when_root_already_exists`; `test_consumed_predecessor_cli_route_is_retired`; `test_create_only_writer_preserves_collision_and_cli_has_no_period_override` |
| Authenticated development-evidence binding; exact calendar-derived later-period completeness and STRESS thresholds; candidate/economics/P&L integrity; ordered holdout → extension → survivor boundaries; synthetic evidence cannot authorize sealed data | `test_synthetic_development_report_cannot_issue_authenticated_evidence`; `test_later_period_calendar_population_and_non_authorizing`; `test_later_period_completeness_candidate_and_economics_bindings_fail_closed`; `test_holdout_stress_thresholds_produce_typed_rejections`; `test_extension_stress_thresholds_produce_typed_rejections`; `test_later_period_authorization_requires_real_source_owned_ordered_evidence`; `test_holdout_boundaries_accept_inclusive_limits` |

The E1-C3 finite-precision regression replays 210 synthetic BASE trades through the real fill and year-accounting paths. At 60 digits, the ending-equity return is `5E-60` below the difference of separately summed realized gains and losses. The fold accepts the exactly reconciled cash chain. A separate regression changes one trade's P&L by `0.01` and rebuilds the year totals. The unchanged fill cash still causes rejection. The later-period entry-limit regression covers all four families for both diagnostic periods using synthetic frozen candidates.

### E2 full-development custody correction

The consumed first real development observation was read-only verified before implementation and is preserved unchanged at `F:\AI\temp\arch151-intraday-development-evidence`:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `attempt.json` | 381 | `181479c21ed663f38c6df563917e767dcc4d2b11caf195d300c39d9f44661465` |
| `source-revision.json` | 413 | `0c25ffa671bcfc72e9e9ac5b233b534d3e7d78847a996b76ae91ef28f7c6a68c` |
| `operator-failure.json` | 376 | `7c5a76452e8811cdf9a2bfe8e75e0bd2ff44f47e51a2c1d140bc3f6df4980ee8` |
| `attempt-result.json` | 931 | `0e0e5d5bfe3e8f0c6d04159c6615bccaa92a067f7e54dde42ce3b2d254a088e2` |

The records cross-bind attempt `0c0db97e-034c-4b59-97de-137d6e95359c`, invocation `7fa05c82-d0e5-508f-8e77-b508071236d0`, source `3bb821aa77fbad7f3177e880d64234eb66b68ec4` / tree `5e559e406d66f5a3bcbbab5155db0688b1c4c1d2`, and terminal `FAILED / SOURCE_LOAD_FAILED`. Attempted years and year artifacts are empty, candidate evaluation is `NOT_EVALUATED`, report/source-binding IDs are null, and retry is forbidden. The sanitized artifact identifies only `AuthorizationUnavailableError`; it does not establish the exact raising statement or exception text, and it is not a negative strategy result.

The E2 source correction was accepted at `7c9c398cd82f917b51ce4ddba5488df937ea46ac` / tree `d2e3067a285cc309fea6989f145203b08e86eabd`; feature FULL `45769306690` and develop exact reuse `45772034607`, both attempt 1, were terminal SUCCESS. E2's later consumed one-shot observation is preserved at `F:\AI\temp\arch151-intraday-development-evidence-e2-successor`: attempt `8721f462-ebeb-4f77-b5b7-4455e30cb599`, invocation `89f2b597-3032-5502-bfd4-33608c3f234b`, predecessor binding `5ce662be-6d80-5b6c-a626-769714cd3ca3`, SHA-256 `78fda36898519a1aca5f0866ba7d68fd55e1d0aa4625e0294df94d36d94e49e7`.

| E2 artifact | Bytes | SHA-256 |
|---|---:|---|
| `predecessor-binding.json` | 1156 | `78fda36898519a1aca5f0866ba7d68fd55e1d0aa4625e0294df94d36d94e49e7` |
| `attempt.json` | 541 | `8936e301d899fe2c07178c22ee3e8c21f90ba9dd3bfd90c60cdebe3ca33f0834` |
| `source-revision.json` | 573 | `f97351bc52637342bfed0e3eb707b7dc3954a77e1bb9468ca0138404509da40e` |
| `operator-failure.json` | 519 | `07d7d4c266aafcb43a2b8df697ece446928f7f2738626a765ffdfc26075a316e` |
| `attempt-result.json` | 1155 | `472d7d9d5c7c2dad3c07998b451b808e32d8c0f8ffa89d8074032a422897d252` |

E2 terminated `FAILED / UNCLASSIFIED_FAILURE`, exception type `ValueError`, source digest `69537a0b180bf995f1e645bda5e7b25fc32f66d2f5c6104a407d57e764a7b40b`, zero completed annual artifacts, null source-binding/report IDs, `NOT_EVALUATED`, and `automatic_retry=FORBIDDEN`. The digest establishes that source loading and source-history construction returned. The failure occurred before annual evidence completed; evidence does not distinguish annual simulation from evidence construction. The exact raising statement is unknown. Neither E1 nor E2 failure is a negative strategy result.

Source inspection and the synthetic regression reproduce the incompatible windows: Arch150's accepted `open_sparse_discovery_dataset` clips its `DISCOVERY` result at 2021-01-01, but the former Arch151 check required a 2024-01-01 end. The corrected Arch151 adapter consumes the complete output of Arch150 `_validate_accepted_sparse_custody` directly. It retains full-window validated bars, exact normalized CSV commitments and pinned artifact inventory, accepted semantic identities, SPY-then-QQQ ordering, and `ValidatedUniverseBars.input_digest`; Arch150's stage firewall is unchanged. It converts those exact bars to one-minute Arch151 bars, verifies conversion against the full source, and constructs source-owned sparse streams, verified seals, and VWAP. History material and the derived history-ID namespace advance to v2 because the complete-input digest now defines source identity. The consumed attempt issued no real Arch151 history identity; frozen strategy, manifest, ledger, economics, thresholds, and DSR identities are unchanged.

The positive regression substitutes only the external artifact reader and a distinct typed synthetic custody-validation boundary. The corrected window and authority checks, normalized-bar conversion, full-input digest, source binding, projection construction, feature preparation, and actual B5 slot replay remain active. Its result is explicitly `SYNTHETIC_TEST_ONLY`; `evaluate_full_development_history` rejects it, so the synthetic run cannot issue authenticated development or holdout authority. Negative regressions cover truncated bars, reordered or interleaved symbols, reordered observations, 2024 input, malformed or incorrect artifact commitments, unknown authority, and projection/source mismatch. E2 recorded adapter load failures as closed reason codes (`ARTIFACT_AUTHENTICATION_FAILED`, `INVALID_DEVELOPMENT_POPULATION`, `CUSTODY_AUTHORITY_MISMATCH`, `SOURCE_PROJECTION_CONSTRUCTION_FAILED`) in operator failure schema v2; raw exception text was not recorded. The original v1 predecessor artifacts remain readable with their original broad `SOURCE_LOAD_FAILED` classification.

Both E1 and E2 public execution routes are permanently retired. E2 `--preflight-successor` and `--run-successor` calls return `SUCCESSOR_ATTEMPT_CONSUMED` whether the old root exists or not; they do not recheck source, read custody, or create an attempt. The private engine remains synthetic-test-only. Both consumed roots and their evidence are immutable. No retry, resume, recovery, relocation, or replacement observation is authorized by this validation plan.

Foundation predicate reachability fixtures use synthetic completed bars. Evaluator fixtures then drive the accepted family predicates through the chronological synthetic one-minute loop, simulated fills, per-slot capital accounting, session returns, and report composition. No test opens accepted custody or executes a real-data replay.

Canonical year-batch identity uses v3 and binds complete replay-output digests plus the source-bound annual SPY benchmark identity. Fold evaluation and qualification identities remain v3; development-run identity uses v4 and the canonical report uses `arch151-development-evaluation-report/v3`. The report hashes canonical JSON bytes and includes all 480 fold records, 480 annual diagnostics, 96 five-year diagnostics, cost-path comparisons, and annual plus aggregate SPY adjusted-price benchmarks. Trade excursion fields enter replay digests. Regression fixtures retain predecessor year-batch v2, run v3/v2, report v2/v1, fold v2, and qualification v2 schema references. DSR calculation v2 and the 29/64 ledger are unchanged. Program, slot, manifest, qualification, DSR, and freeze identities do not change in this phase; year-batch IDs and derived run/report IDs change. No real evaluation batch, run, or report existed to remap. Synthetic source binding is labeled `SYNTHETIC_TEST_ONLY` and cannot be used as accepted Arch150 custody evidence.

### Generated workload and bounded reuse evidence

### E3 numerical and reliability correction

The Family A source-path regression uses 60 complete synthetic historical minute sessions with a nonterminating 3-to-4 opening ratio and a high-precision fractional entry. It reproduces the prior constructor failure through `family_a_initial_risk`, verifies that validation recomputes the producer's exact forward stop under the fixed 60-digit context, checks strict `stop < entry`, rejects positive distance tampering and rounded-away distance, and compares results under normal and precision-8 ambient contexts. A separate actual stop-gap replay creates fractional negative trade P&L; `_economic_diagnostic` must report its exact `copy_negate()` loss under precision 8.

The five-year canonical campaign retains its existing 480-record composition test and now enriches only its 2023 source-owned synthetic fixture. It runs the full 96-record 2023 annual batch once under ambient precision 8 and uses actual source-derived Family A measures from historical synthetic minutes. Adding `0.03125` to the representative A OHLC prices gives a nonterminating calibration ratio `0.1 / 100.03125`, asserted at the frozen precision. Ten distinct signal sessions cover sixteen program/symbol representatives across all four families, both symbols, 5-minute and 15-minute resolutions, and ZERO/BASE/STRESS; the SPY B5-01 annual replay contains trades on multiple sessions. The test compares the low-ambient annual results against normal-context execution from shared source-bound calibration/preparation caches and one reference tape per selected slot/session, serializes the actual annual evidence through `_year_batch_material` and canonical bytes, composes all five years, and serializes the development report. It performs no second campaign.

Failure regressions distinguish source-load and annual-simulation stages, preserve E1's exact historical binding, and prove that E1/E2 public execution routes stay consumed even when the E2 root is absent. An injected annual replay exception records year, slot/program, symbol, operation stage, closed reason, repository function, and safe relative source location without the exception message. A chained `EvaluationIntegrityError` retains its preexisting failure code. These fixtures do not validate production-scale runtime, accepted-custody replay results, provider behavior, or sealed later periods.

### Generated workload and bounded reuse evidence

The five-year correctness regression runs the canonical simulator and composer on generated SPY/QQQ signals and exact SPY benchmark endpoints. It verifies the ordered 96 slot/economics records per batch, trades in all three economics cases, all 480 composed records, and exact synthetic source binding from history through replay and composition. Separate regressions compare Family A calibration and Family D pair-cache reuse against independent reconstruction. The correctness regression uses no memory tracing.

The predecessor 20-session workload (four complete synthetic XNYS sessions per year and 15,600 one-minute bars) remains historical performance evidence. At predecessor E1-C1, with `tracemalloc` active during simulation and composition, the recorded end-to-end time was 181.954 seconds. Per-year simulation times were 30.379, 31.248, 31.001, 31.269, and 31.999 seconds, and peak traced allocation was 60.20 MiB. The measurement started after history construction and measured Python allocations. The predecessor test set no performance threshold.

For capacity planning, the prior linear extrapolation from 20 to 1,258 scored sessions gave 11,445 seconds (3.18 hours) at a constant per-session cost. Sparse generated data and allocation tracing limit that estimate. The trace is preserved as historical evidence and has no recurring certification invocation.

The preserved E1-C1 broad-6 artifact from run `45715017377` measured 761.848
seconds wall time, of which 583.460 seconds were attributed to evaluator tests.
The E1-C2 focused JUnit estimate for that module is 155.059 seconds, substituting
targeted recheck timings for revised tests. This estimates the old broad-6 at
333.449 seconds. Adding that measured weight to the existing placement inputs
yields seven nonempty lanes with a maximum modeled weight of 291.980 seconds.
A separate projection sums prior hosted case timings by the new lane membership,
uses the focused measurements for the changed Arch151 modules and adds the
largest prior lane overhead (18.381 seconds) to each lane. It estimates a
249.0-second maximum, with the evaluator in broad-1. Those estimates combine
different Windows hosts and do not establish actual hosted certification time.
The lane algorithm, frozen C4 timing evidence and 300-second wall ceiling remain
in force.

### E3-C1 certification timing correction

E3 mapped FULL run `45797405811`, attempt 1, is preserved as a terminal
certification-budget failure. Broad-1 completed 2,443 cases (2,442 passed,
one skipped, zero failures or errors) in 408.168 seconds against the unchanged
300-second limit. Failed job `139831883414` contains timing artifact
`15106217058`; the six other lanes passed. This is not a source-test failure
or an accepted certification result. The prepublication timing audit did not
account sufficiently for the expanded campaign fixture's actual hosted cost;
the complete hosted overrun is not claimed to be reproduced locally.

The E2-to-E3 broad-1 case sum rose from 233.901 to 393.199 seconds
(+159.298); measured runner overhead rose from 12.070 to 14.969 seconds
(+2.899), yielding the 162.197-second wall increase. The evaluator module rose
from 161.542 to 288.809 seconds (+127.267). Its five-year campaign case rose
from 13.341 to 92.025 seconds (+78.684); the evaluator's remaining cases
accounted for another 48.583 seconds of increase. The other 49 broad-1 module
groups rose from 72.359 to 104.390 seconds (+32.031). Their largest increases
included the Arch134 successor soak (16.565 to 23.006), Arch149 rotation
(7.475 to 11.469), certification results (4.358 to 7.886), and filtered trend
bundle (8.418 to 11.763). The broad distribution is consistent with shared
setup or host sensitivity; these records do not prove a particular cause.

E3-C1 removes redundant generated-history construction while retaining the
same canonical annual and campaign path. Raw minutes now feed one final
synthetic history instead of repeatedly sealing intermediate histories and
extracting their projections. It keeps complete prior Family A sessions for
calibration, exact 15-minute benchmark endpoint buckets, all 16 representative
program/symbol sessions across the four families, SPY and QQQ, both resolutions,
all three economics cases, the complete 96-record annual result, and the
canonical 480-record composition/report serialization. Sparse target sessions
include only strategy observations plus the exact scheduled liquidation-minute
observation for each symbol that can carry a position, preserving actual
mandatory-liquidation checks. The Arch150 adapter fixture retains complete
representative dates before and after 2021 and the real synthetic B5 replay;
it no longer builds 60 unused complete sessions. Its positive authority checks
and invalid/truncated/mismatched/sanitized rejection cases remain. The Family A
canonical-signal fixture reuses source-owned calibration/preparation caches and
replays the selected BASE session once, while the five-year campaign remains
the separate annual/cost integration proof.

The attestation test seeds a test-local identity cache from `idle_report`, which
was produced by the real canonical serializer for that exact immutable run.
Both issuer and valid validator paths still request serialization of the exact
run; another run falls through to the real serializer. The byte hash check,
issuer/validator binding, changed-revision rejection, forged-report rejection,
annual serialization, and campaign serialization remain exercised. No
successful issuer or validator result is mocked.

Matched local fixture-only construction used the published E3 test blob and
the E3-C1 test file in separate fresh Python processes with the same interpreter
and working directory; the timer covered only `_synthetic_five_year_campaign_history()`
and not imports or replay. It fell from 37.676 to 18.335 seconds, with 16
representative sessions in each result. The campaign pytest case measured
91.96 seconds in the selected E3 run and 65.46 seconds in the selected E3-C1
run; these case timings include order-dependent cached fixture setup and are
reported separately from the isolated constructor measurement. The four
invalid-population adapter cases measured 13.17 seconds against the immutable
E3 test blob and 0.72 seconds in E3-C1 (all four passed). A cold standalone
SPY/A5 canonical-signal case measured 18.01 and 17.17 seconds respectively;
the hosted E3 case was 2.041 seconds after earlier module setup, so no Family A
savings are projected from the cold comparison.

Other paired focused local cases were: full-input adapter 25.41 to 2.01
seconds; truncated-population boundary 11.53 to 6.41 seconds; sanitized
projection failure 4.19 to 0.10 seconds; and mismatched authority/projection
source 3.77 to 0.06 seconds. The exact-run attestation call fell from 53.18 to
0.42 seconds after seeding the test-local cache from the real `idle_report`;
its real report-fixture setup remained about 32 seconds in both selections.
These are separate focused-process measurements, not a claim that all setup
cost is eliminated.

Using the E3 hosted evaluator case sum and conservatively projecting measured
local ratios for the campaign, adapter cases, invalid-population cases, and
identity-seeded attestation gives a 150.394-second evaluator estimate. Keeping
all other E3 broad-1 testcase durations fixed gives 254.784 seconds of testcase
work; adding E3's unchanged 14.969-second maximum overhead gives a 269.753-second
observed-shape projection, 30.247 seconds below the existing ceiling. This is
a projection, not a certification result. The current C4 source model remains
unchanged: broad-1 is 291.973 seconds and the seven-lane maximum is 291.980
seconds. No timing weights, frozen C4 rows, lane membership, or budget were
changed; mapped GitHub FULL remains the final timing gate.

## 3. Source-only checkpoint and mapped certification

The established source-foundation checkpoint remains `arch151-intraday-walkforward-foundation` on branch `feature/research-arch151-intraday-walkforward-current`, preserving its prior route and certification evidence. The existing evaluator checkpoint `arch151-intraday-walkforward-evaluator` remains the source-only route for bounded Arch151 evaluator/operator corrections, including E3; this does not create another checkpoint registration. Changed-path routing selects the evaluator when its source/test or Arch151 design/validation docs are present, including mixed runner/workflow/docs changes; a no-diff route lookup keeps the foundation default. Both specs use `preflight=None`, `execute=None`, and `remote_head_env=None`, have no protected-effect dispatch, and map to GitHub-owned canonical `full`. Neither is registered in the historical `ACTIVE_CI_CHECKPOINTS` tuple.

Route and current-authority tests reside in:

- `tests/runtime/checkpoint_runner/test_core.py` — source-only checkpoint registration, route ownership, and no protected execution surface.
- `tests/runtime/checkpoint_runner/test_ci.py` — active source-gate route, push association, FULL profile ownership, and current job-topology/coherence checks.
- `tests/runtime/checkpoint_runner/test_source_authority.py` — current authority projections and preservation of immutable historical security/source pins.

The evaluator route owns `tests/experiments/test_arch151_intraday_walkforward_evaluator.py` and `tests/experiments/test_arch151_intraday_walkforward_operator.py`; its Ruff ownership includes both operator paths. The foundation and evaluator both retain the focused foundation module and current runner authority tests. Current route tests exercise default foundation selection, foundation-only changed paths, evaluator/operator-source selection, mixed evaluator/foundation/runner/workflow/docs paths, and pull-request rejection. Historical predecessor source pins remain exact and unchanged.

Neither current route is registered as a historical ACTIVE_CI checkpoint. Current mutable routing/topology tests assert ownership and expected relationships rather than freezing unrelated mutable module inventories.

## 4. Focused local verification

E3 changed the numerical evaluator and operator paths. E3-C1 changes only the evaluator's synthetic test fixtures and the owning coordination/validation documents; it does not change executable source, current runner, shared authority, or certification timing inputs. Focused verification selects the generated five-year campaign, canonical strategy signals, Arch150 adapter boundaries, exact-run attestation/report, and relevant numerical diagnostics. Do not rerun local canonical FULL; the registered mapping assigns FULL to GitHub.

```powershell
$python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
$projectRoot = 'F:\AI\worktrees\ai-trading-bot-arch151-intraday-walkforward-current'
$pytestBase = Join-Path 'F:\AI\temp\pytest' ('arch151-e3c1-' + [guid]::NewGuid().ToString('N'))
& $python -m pytest -q -p no:cacheprovider `
  -c (Join-Path $projectRoot 'pyproject.toml') `
  --rootdir $projectRoot "--basetemp=$pytestBase" `
  (Join-Path $projectRoot 'tests/experiments/test_arch151_intraday_walkforward_evaluator.py') `
  -k 'generated_five_year_simulation_composes_non_idle_480_records or all_canonical_signals_enter_and_exit_through_unmocked_predicates or arch150_full_input_adapter_preserves_development_history_and_replays or arch150_adapter_rejects_invalid_population_before_custody_scan or arch150_adapter_rejects_truncated_population_at_custody_boundary or arch150_adapter_rejects_mismatched_authority_and_projection_source or arch150_adapter_sanitizes_projection_construction_failure or operator_attestation_binds_exact_run_report_and_captured_revision or source_owned_report_binds_all_records_provenance_dsr_and_freeze or economic_diagnostic_negates_fractional_losses_exactly or family_a_calibration_cache_matches_per_program_reference')
if ($LASTEXITCODE -ne 0) { throw "Focused pytest failed with native exit $LASTEXITCODE" }

& $python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "Ruff check failed with native exit $LASTEXITCODE" }
& $python -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed with native exit $LASTEXITCODE" }
git diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed with native exit $LASTEXITCODE" }
```

Use the repository-approved interpreter resolved to this checkout and a fresh GUID basetemp under `F:\AI\temp\pytest` for each pytest invocation. Earlier E1/E2 hosted counts and timing measurements in this document remain historical evidence; E3's preserved terminal failure and the E3-C1 focused measurements above are separate evidence. The mapped canonical FULL remains GitHub-owned, with the existing seven-lane topology and 300-second certification ceiling unchanged. Do not run local canonical FULL for this mapped checkpoint.

The route and GitHub-owned canonical FULL profile are specified in §3. Mapped certification is tied to the exact source revision; terminal CI evidence does not assert ChatGPT acceptance or develop integration.

## 5. Remaining holdout and extension authority boundary

The offline development evaluator, canonical report, and source-owned authenticated development-evidence issuer are implemented. E2 loaded the authorized 2016–2023 source and then failed before producing a completed annual artifact; E3 performed no custody-content read or real replay. Both E1 and E2 public execution routes are permanently retired, and the consumed attempts must remain unchanged. No new diagnostic route is implemented here. The bounded reusable diagnostics proposal is described in Architecture §9 and requires separate ChatGPT review before implementation. The following capabilities remain unavailable and require separate authorization before either sealed later period can be opened:

- A future reviewed offline diagnostic invocation may use only authenticated 2016–2023 source history and must retain exact source/custody provenance, complete 32-slot × 3-economics annual populations, and partial evidence. Diagnostic outputs must not issue a source attestation, qualify candidates, or authorize holdout; no such route exists or was run in E3.
- The source-owned evidence issuer is exercised only with synthetic rejection tests in this pass. A future accepted-source run must produce and bind its exact report, all 480 records, complete freeze/DSR evidence, and clean source revision before holdout authorization can be issued.
- Authenticated holdout result issuance and a reader remain unavailable. The pure `qualify_later_period` function derives the exact 502-session/24-month 2024–2025 population from the published XNYS schedule and checks STRESS net return >0, each year >0, PF >1.10, drawdown <=15%, active-session fraction >=30%, average completed round trips/year >=80, and no month >40% of positive realized net trade P&L. Its synthetic PASS is not authenticated and cannot open data. No strategy mutation is allowed after holdout visibility.
- Authenticated same-candidate Jan–Oct 2026 extension result issuance and a reader remain unavailable. The pure qualifier checks the exact 204-session/10-month XNYS population and STRESS net return >0, PF >1.05, drawdown <=15%, at least 6/10 complete calendar months positive, and active-session fraction >=30%. Extension authorization requires the same candidate and an authenticated holdout PASS; pure synthetic output cannot satisfy that boundary. A resulting `ARCH151_INTRADAY_RESEARCH_SURVIVOR` classification permits only a separately authorized paper/shadow translation study and grants no runtime, order, Robinhood, or live authority.

Synthetic source and evaluator records test pure formulas, threshold boundaries, replay ordering, result serialization, and fail-closed rejection. They do not create accepted-custody evidence, a real-data qualifying candidate, holdout or extension permission, or authority to access later data. E3's mapped CI failure is recorded above. The E3-C1 mapped result is owned by its exact GitHub run and does not itself establish source acceptance or develop integration.
