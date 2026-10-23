# Architecture 132-R3K — ROBINHOOD four-lane current-local validation

## Scope and evidence

R3K is a topology-only successor to published R3J. It is based on exact R3J
HEAD `de627d741891972b35fec458dbb9e66d46d1f4ac` / tree
`45bf73e5136d69ae8a1e1246340ac3b4f6791f41`. It does not change D1S3 product
behavior, FULL placement or timing, LEGACY, EXHAUSTIVE, ownership, protected
authority, or the parked unpublished R4 worktree.

The sole evidence source is the preserved R3J-D1 isolated diagnostic directory:

```text
F:\AI\temp\certification\arch132-r3j-d1-isolated-186da70cc66942dfb26a763f150958f6
```

The two isolated XML files and `analysis.json` reconcile to 109 unique
canonical modules and 856949 ms raw testcase work. Exactly one raw module is
zero: `tests/domain/test_positions.py = 0 ms`. R3K normalizes only that raw
zero to the reviewed positive minimum of 1 ms before freezing source data.
The canonical source model therefore has 109 positive integer entries and
856950 ms total. Runtime validation remains strict and rejects a directly
supplied zero.

Canonical sorted compact JSON timing-map SHA256:

```text
0c0c79f710ab8b3a9ffc08de4720c026f257e2ffefc8dc6989c3a70fba2d2898
```

The source table is tuple material of canonical paths and positive integer
milliseconds. Duplicate paths, malformed entries, stale paths, nonpositive
values, and bool values fail closed. A future selected module absent from the
table receives the positive 1000-ms fallback. Placement never reads file size,
mutable timing files, prior JUnit/CI artifacts, clocks, or adaptive state.

## Exact four-lane model

The unchanged greedy algorithm sorts by descending weight then canonical path,
assigns each whole module to the lowest modeled total with lowest lane index as
the tie-break, and preserves assignment order. On the exact 109-module
inventory, reversed input produces the same result:

| Lane | Modules | Modeled ms | Ordered membership SHA256 |
| --- | ---: | ---: | --- |
| robinhood-1 | 27 | 214237 | `cc0a6556faf54386fe4e8c0a192ac0ad6543da814d5926e86f7c8bc867470a51` |
| robinhood-2 | 30 | 214237 | `904166863dfa5354fad29773877c70eb991ba240b3f117ccb163766f8fc71198` |
| robinhood-3 | 26 | 214240 | `a5620743bd21fbb59d16f0994290e2908bfeeba71bfc3a15bed0fb2cadb42aa3` |
| robinhood-4 | 26 | 214236 | `e51754fe142e84fac06f2a27184aa948f1a2de73f5868f6fef45f3d174a62b45` |
| **total** | **109** | **856950** | — |

The exact ordered membership is:

```text
robinhood-1:
tests/review_paper/test_d1_session_execution.py
tests/runtime/checkpoint_runner/test_arch133_h_k.py
tests/review_paper/test_arch133_closed_descendant_rename_qualification.py
tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py
tests/runtime/checkpoint_runner/test_ci.py
tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py
tests/test_robinhood_supervised_qualification.py
tests/review_paper/test_alpaca_credential_generation.py
tests/review_paper/test_alpaca_credential_staging_cleanup.py
tests/review_paper/test_pre_market_wake_qualification.py
tests/review_paper/test_unattended_one_wake.py
tests/review_paper/test_unattended_host.py
tests/robinhood_mcp/test_windows_oauth.py
tests/review_paper/test_production_strategy_prepare_operator.py
tests/review_paper/test_supervised_release_foundation.py
tests/review_paper/test_supervised_forward_paper.py
tests/review_paper/test_arch133_reprovision_admission_diagnostic.py
tests/review_paper/test_scratch_root_acl.py
tests/review_paper/test_published_session_prepare.py
tests/review_paper/test_store.py
tests/review_paper/test_risk_prices.py
tests/test_robinhood_paper_pipeline.py
tests/execution/test_paper_submission.py
tests/execution/test_portfolio_orders.py
tests/risk/test_risk_models.py
tests/ledger/test_models.py
tests/domain/test_positions.py

robinhood-2:
tests/review_paper/test_five_session_soak.py
tests/review_paper/test_five_session_soak_child.py
tests/review_paper/test_arch133_reprovision_recovery.py
tests/runtime/checkpoint_runner/test_arch133_a_g.py
tests/review_paper/test_pre_market_wake_overnight.py
tests/review_paper/test_d1_session_authorization.py
tests/review_paper/test_production_paper_runtime.py
tests/review_paper/test_publication_state_paper_corrected.py
tests/review_paper/test_supervised_release_publication_recovery.py
tests/review_paper/test_unattended_execution.py
tests/runtime/checkpoint_runner/test_core.py
tests/scripts/certification_runner/test_profiles.py
tests/review_paper/test_supervised_release_installation.py
tests/review_paper/test_arch133_parent_policy_diagnostic.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_prepare_qualification.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_retained_root_acl_recovery.py
tests/test_robinhood_paper_cycle.py
tests/scripts/certification_runner/test_children.py
tests/test_robinhood_prepare_operator.py
tests/ledger/test_checkpoint_state.py
tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py
tests/domain/test_proposals.py
tests/robinhood_mcp/test_account_resolution.py
tests/execution/test_execution_models.py
tests/ledger/test_initialization.py
tests/domain/test_market.py
tests/domain/test_orders.py
tests/robinhood_mcp/test_adapter.py

robinhood-3:
tests/runtime/checkpoint_runner/test_arch133_l_m.py
tests/review_paper/test_supervised_release_bundle.py
tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py
tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py
tests/review_paper/test_production_paper_runtime_acl.py
tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py
tests/review_paper/test_arch133_reprovision_reconciliation.py
tests/scripts/certification_runner/test_lanes.py
tests/review_paper/test_post_publication_stage_diagnostic.py
tests/review_paper/test_supervised_maintenance_rebind.py
tests/test_robinhood_prepare_qualification_verifier.py
tests/review_paper/test_arch134_f1r1_d1s2_successor_readiness.py
tests/review_paper/test_supervised_runtime_host_admission.py
tests/review_paper/test_current_production_strategy_decision.py
tests/review_paper/test_arch133_parent_security_diagnostic.py
tests/review_paper/test_risk_context.py
tests/review_paper/test_strategy_market_history.py
tests/test_robinhood_forward_paper_cycle.py
tests/review_paper/test_retained_root_diagnostic.py
tests/review_paper/test_performance.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_intent_bridge.py
tests/execution/test_paper_fill_application.py
tests/ledger/test_ledger.py
tests/risk/test_manager.py

robinhood-4:
tests/runtime/checkpoint_runner/test_arch131.py
tests/review_paper/test_arch133_scheduler_installation.py
tests/review_paper/test_supervised_release_installation_operator.py
tests/review_paper/test_arch133_windows_rename_qualification.py
tests/review_paper/test_arch133_fresh_activation_reprovision.py
tests/review_paper/test_armed_production_paper_session.py
tests/review_paper/test_supervised_deployment_qualification.py
tests/review_paper/test_alpaca_authentication_qualification.py
tests/review_paper/test_publication_state_paper_diagnostic.py
tests/scripts/certification_runner/test_results.py
tests/review_paper/test_post_publication_verifier.py
tests/review_paper/test_unattended_state_store.py
tests/review_paper/test_unattended_publication.py
tests/test_robinhood_live_qualification_verifier.py
tests/review_paper/test_history_qualification.py
tests/test_robinhood_paper_operator.py
tests/review_paper/test_supervised_release_installation_reconciliation.py
tests/scripts/certification_runner/test_source.py
tests/review_paper/test_arch134_f1r1_b_host_qualification.py
tests/review_paper/test_unattended_activation.py
tests/review_paper/test_production_strategy_cycle.py
tests/robinhood_mcp/test_historical.py
tests/robinhood_mcp/test_sdk_transport.py
tests/execution/test_paper_fills.py
tests/execution/test_order_engine.py
tests/risk/test_orchestration.py
```

## Rejected topology and acceptance boundary

Raw two-lane work has a lower bound of 428474.5 ms. Raw three-lane work has a
lower bound of 285649.667 ms; the normalized source model is 285650 ms. That
leaves only about 14.35 seconds below the unchanged 300-second ceiling. The
isolated child/process overhead was already approximately 8.197 s and 8.422 s,
and the observed two-child concurrent slowdown was +7.960% JUnit work and
+8.337% child elapsed. Three lanes therefore lack credible margin and are
documented only, not implemented or attempted. R3K selects four directly and
does not add a fifth-lane fallback.

Historical lane pins remain unchanged and inactive. Ownership and coverage
remain unchanged: all 109 selected modules run exactly once, with no overlap.
R3K is intentionally absent from `ACTIVE_CI_CHECKPOINTS` and
`CI_CERTIFICATION_PROFILES`; resolving its push branch returns `None`. The
300-second ceiling remains frozen. No FULL or protected operation is part of
R3K.
