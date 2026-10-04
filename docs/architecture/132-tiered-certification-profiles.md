# Architecture 132 — Tiered certification profiles

## Scope and policy

Retain complete repository certification while reducing routine pytest breadth
at coherent Robinhood integration boundaries. This is a source/test-only
milestone. Four source-verification levels are FOCUSED, SOURCE-GATE CI,
ROBINHOOD, and FULL; PROTECTED is a separate authorization boundary.

| Level | Trigger |
| --- | --- |
| FOCUSED | Every implementation/correction. Codex runs affected tests and focused checks. |
| SOURCE-GATE CI | Every pushed registered checkpoint. Existing registered GitHub source-gate batching remains accepted. |
| ROBINHOOD | When ChatGPT declares a coherent Architecture 131 integration boundary; before protected Robinhood qualification; after material changes to shared domain/execution/ledger/risk foundations used by Architecture 131. |
| FULL | After certification-topology changes; before major develop/release integration; before consequential production/live-readiness transitions; after sufficiently broad shared-core changes; or when ChatGPT explicitly determines accumulated checkpoints warrant repository-wide regression. |
| PROTECTED | Always separate fresh authorization. |

Full repository certification is intentionally retained, but is not required
after every accepted source checkpoint. FULL is not mechanically tied to every
Architecture 131 letter/checkpoint. ChatGPT owns exact source review, acceptance,
and the certification-tier decision. The normal handoff remains:

```text
implementation + focused checks
-> exact-file commit/push
-> ChatGPT exact GitHub code review
-> source acceptance
-> appropriate certification tier
-> docs closeout (PROJECT_STATUS + HANDOFF)
```

Local patch-first review remains fallback-only. This milestone changes neither
`scripts/checkpoint_runner.py` nor `.github/workflows/checkpoint-source-gates.yml`.
Topology changes trigger FULL after review; neither actual certification
profile is run as part of this bounded implementation.

## CLI and full-profile compatibility

`scripts/run_test_certification.py` accepts `--profile full` and
`--profile robinhood`; unknown profiles are rejected. Omitting `--profile`
continues to mean `full`.

FULL discovers every `tests/**/test_*.py` module, separates the exact existing
five-module safety allowlist, and balances the remainder by descending file
size, with stable path and lane ties. Its exact lanes remain `broad-1`,
`broad-2`, and `serial`. The serial allowlist remains:

```text
tests/runtime/test_windows_transactional_capture_authority.py
tests/runtime/test_windows_authority_schema.py
tests/runtime/test_windows_authority.py
tests/runtime/test_windows_effectful_capture_native_acceptance.py
tests/acceptance/test_windows_authority_provisioning_acceptance.py
```

No full module coverage or serial safety requirement is removed.

## Robinhood ownership and frozen baseline

Owned directory patterns:

```text
tests/domain/test_*.py
tests/execution/test_*.py
tests/ledger/test_*.py
tests/risk/test_*.py
tests/review_paper/test_*.py
tests/robinhood_mcp/test_*.py
```

Root ownership is `tests/test_robinhood_*.py`. Exact infrastructure ownership is
`tests/runtime/test_checkpoint_runner.py` and
`tests/scripts/test_run_test_certification.py`. These patterns select direct
files in the named directories. Newly added matching files are admitted
automatically. All modules in the baseline below remain required: deletion or
renaming fails closed even if another owned file replaces them.

At accepted HEAD `69327a7d5fbea7499329902ff96fd98e77a62591`, tree
`8e39547005c320387ef231c8dfd5e914d2f02322`, the exact baseline is 40 modules:

```text
tests/domain/test_market.py
tests/domain/test_orders.py
tests/domain/test_positions.py
tests/domain/test_proposals.py
tests/execution/test_execution_models.py
tests/execution/test_order_engine.py
tests/execution/test_paper_fill_application.py
tests/execution/test_paper_fills.py
tests/execution/test_paper_submission.py
tests/execution/test_portfolio_orders.py
tests/ledger/test_checkpoint_state.py
tests/ledger/test_initialization.py
tests/ledger/test_ledger.py
tests/ledger/test_models.py
tests/review_paper/test_forward_preview.py
tests/review_paper/test_intent_bridge.py
tests/review_paper/test_nyse_published_regular_sessions.py
tests/review_paper/test_performance.py
tests/review_paper/test_prepare_qualification.py
tests/review_paper/test_risk_context.py
tests/review_paper/test_risk_price_acquisition.py
tests/review_paper/test_risk_prices.py
tests/review_paper/test_session_admission.py
tests/review_paper/test_store.py
tests/review_paper/test_supervised_forward_paper.py
tests/risk/test_manager.py
tests/risk/test_orchestration.py
tests/risk/test_risk_models.py
tests/robinhood_mcp/test_account_resolution.py
tests/robinhood_mcp/test_adapter.py
tests/robinhood_mcp/test_sdk_transport.py
tests/robinhood_mcp/test_windows_oauth.py
tests/runtime/test_checkpoint_runner.py
tests/scripts/test_run_test_certification.py
tests/test_robinhood_forward_paper_cycle.py
tests/test_robinhood_live_qualification_verifier.py
tests/test_robinhood_paper_cycle.py
tests/test_robinhood_paper_operator.py
tests/test_robinhood_paper_pipeline.py
tests/test_robinhood_prepare_qualification_verifier.py
```

All current Architecture 131 registered test modules are included. Tests may
inspect checkpoint registrations to prove coverage; production certification
code does not depend on private checkpoint-runner helpers.

Historical Windows/D10 serial modules are excluded unless a future explicit
contract changes ownership. Unrelated GUI, CLI, backtesting/research,
market-data/Alpaca, personal-desktop/D10, and Windows production-authority
families are excluded.

## Lanes and result accounting

Robinhood runs exactly two deterministic balanced file lanes, `robinhood-1`
and `robinhood-2`, using the existing descending-file-size algorithm. There is
no serial lane. Every lane must be nonempty before any pytest process starts;
empty module lists must never cause accidental repository-wide collection.

Partitions must be complete and disjoint for the selected inventory. Success
requires the exact expected lane names for the chosen profile, successful child
exits and JUnit validation, successful whole-repository static checks, and
unchanged source identity. Missing, extra, or substituted lane names fail.
FULL still requires all three of its exact lanes.

## Source checks, temporary roots, and evidence

Both profiles preserve exact worktree/branch/HEAD/tree/local and live remote
source checks, clean-state admission and post-test/final identity verification,
protected-opt-in rejection, child timeout/failure handling, JUnit/evidence
validation, and external temporary-root requirements. Actual runs require
`F:\AI\temp\pytest`. `--plan` verifies admission and saves evidence without
launching pytest or static checks for either profile.

Post-test static checks remain whole-repository:

```text
ruff check --no-cache .
ruff format --check --no-cache .
git diff --check
```

`results.json` records `profile`, `repository_inventory`, `selected_inventory`,
and `excluded_inventory`. The existing `inventory` remains the flattened
selected lane inventory (unchanged for FULL). Existing lane/source/result fields
remain available.

`inventory.json` retains `all` as the complete repository inventory and adds
`profile`, `repository`, `selected`, and `excluded`. FULL has `selected == all`
and no exclusions. Robinhood shows the bounded selection and every repository
module outside it. Existing `broad`, `serial`, and `lanes` remain: Robinhood's
`broad` is the selected inventory and `serial` is empty metadata, with no empty
serial process. Per-lane logs/JUnit and results continue to live outside the
worktree.

## Protected effects and verification

`PROTECTED_OPT_INS` remains rejected for both profiles, including false-looking
values. Neither profile grants or invokes native Windows acceptance opt-ins,
provider access, Robinhood calls, OAuth interaction, broker effects, or
production effects. PROTECTED always requires separate fresh authorization.

Implementation verification is limited to the certification-runner focused
module (including registered Architecture 131 coverage), directly affected
checkpoint tests if needed, Ruff check/format on changed Python files, and Git
diff checks. Actual Robinhood and FULL certification remain later review-led
operator gates. This implementation does not claim either profile is certified.
