# Architecture 152-PM1 — Portfolio Manager source checkpoint

## Checkpoint identity

- Name: `arch152-portfolio-manager-foundation`
- Feature branch: `feature/robinhood-portfolio-manager-current`
- Reviewed base: `e578a7ff0e128a1f9895a9df82296f73f550e9c5`
- Reviewed base tree: `f6b3036c00afebfce93a1500731e504edba954d4`
- Certification mapping: existing canonical `full` profile, run by GitHub.
- Scope: source-only account-aware Portfolio Manager domain, adapter, durable
  service, synthetic presentation, and tests.

This validation record is prepared with the PM1 implementation. It makes no
claim of source admission, commit, push, source acceptance, terminal CI,
independent review, or integration. Those identities and results are added only
after they exist. Existing Arch151 one-shot evidence and the two preserved
timing failures remain immutable; PM1 does not resume either campaign.

## Current authority and inventory impact

The checkpoint adds the exact PM1 source/test paths to the existing source-only
checkpoint registry, current active-workflow projection, source-authority owner
map, and focused source/Ruff input sets. `resolve_ci_checkpoint` selects PM1 on
the registered feature push and not on pull-request routing. The source
checkpoint has no `preflight`, `execute`, or remote-head environment override.
Its explicit profile is `full`.

`tests/portfolio_manager/` is added as a whole-directory FULL owner. The FULL
122-module and Robinhood 49-module required tuples remain unchanged. There is no
new certification runner or timing topology. The active workflow remains the
seven nonempty, whole-module, deterministic `broad-1` through `broad-7` lanes
with the existing 300-second ceiling and no serial lane.

The route authority checks actual discovered PM tests against current
classification rather than pinning their number. A PM-owned property test
inserts nested synthetic modules, including duplicate basenames, and requires
them to enter FULL and stay out of LEGACY/Robinhood. Existing certification
tests retain their frozen historical bytes and existing growth/collision
coverage. Arch134 historical declarations are reconstructed from their
historical Git objects; current workflow, registry, and certification bytes
are checked through their current semantic owners and projection tests, in line
with Architecture 134 decoupling.

## Focused verification

PM1 verification is limited to the new/changed route, source-authority,
certification-ownership, strict `PortfolioState` adapter, domain, Arch149
adapter, store, application, vertical-slice, and GUI tests, plus focused Ruff
and current authority checks. The existing Arch149 test
`test_terminal_december_no_2024_lookup_and_report_bounds` independently checks
that the frozen exploration ends in December 2023 without a 2024 lookup. Every pytest
invocation uses the shared interpreter
`F:\AI\ai-trading-bot\.venv\Scripts\python.exe`, a fresh GUID directory under
`F:\AI\temp\pytest`, explicit `--basetemp`, `-p no:cacheprovider`, repository
test configuration, and worktree-correct `src` import provenance.

Recorded focused results:

- `tests/runtime/checkpoint_runner/test_core.py::test_arch152_pm1_is_source_only_and_mapped_to_full` and `tests/runtime/checkpoint_runner/test_source_authority.py::test_classification_has_one_current_owner_and_preserves_security_evidence`: 2 passed in 0.25 s. Basetemp: `F:\AI\temp\pytest\arch152-pm1-route-owner-summary-9ad173957b614e81be83b16306a393df`.
- `tests/portfolio_manager/test_adapters.py`: 4 passed in 0.04 s. Basetemp: `F:\AI\temp\pytest\arch152-pm1-portfolio-state-adapters-71fc5d2be2bf4101abaa506175acd866`.
- `tests/portfolio_manager/test_certification_ownership.py`: 1 passed in 0.08 s. Basetemp: `F:\AI\temp\pytest\arch152-pm1-full-ownership-growth-9bd2992896704c1d91309edbfc3e6689`.
- `tests/portfolio_manager/test_arch149_adapter.py`: 2 passed in 1.92 s. Basetemp: `F:\AI\temp\pytest\arch152-pm1-arch149-adapter-5fa0f2b615da4f41b2dcd102d1cd0e1c`.
- `tests/experiments/test_arch149_monthly_defensive_rotation.py::test_terminal_december_no_2024_lookup_and_report_bounds`: 1 passed in 1.06 s. Basetemp: `F:\AI\temp\pytest\arch152-pm1-arch149-firewall-934aedba874a40088105b55002ab2d89`.
- `tests/portfolio_manager/test_observation.py`, `test_decision.py`, and `test_risk_planning.py`: 25 passed in 0.11 s. Basetemp: `F:\AI\temp\pytest\arch152-domain-65c18cc93b3c4da98e8c3be9464431a7`.
- `tests/portfolio_manager/test_store.py`, `test_application_service.py`, `test_vertical_slice.py`, and `test_window.py`: 14 passed in 0.78 s. Basetemp: `F:\AI\temp\pytest\pm1-app-7e598df4bb0d42a987239cb9b2c8cf7f`.
- Domain-focused Ruff check passed; Ruff format check reported 12 files already formatted.
- App/service/UI Ruff 0.17.3 checks passed across the 9 app-owned files; format
  check reported all 9 files already formatted.
- Registry and PM source/test Ruff 0.17.3 checks passed: `ruff check` reported
  all checks passed, and `ruff format --check` reported 31 files already
  formatted.

The absolute-path audit found no new hosted-path assumption in PM tests or the
checkpoint route. The existing `C:\Program Files\Python314\python.exe` in
`test_core.py::test_oversized_windows_ruff_command_preserves_every_path` is a
synthetic Windows command-length fixture. The application’s fixed
`F:\AI\portfolio-manager-state\pm1` root is intentionally local and was not
opened by these focused test commands.

These pytest calls used the shared interpreter and `-p no:cacheprovider`; each
has a separate external basetemp. The Arch149 adapter test uses synthetic
in-memory data strictly inside the frozen 2016–2023 replay boundary. No real
broker/provider, OAuth, credentials, order, production mutation, real
AI-provider request, or Arch149 confirmation access is part of PM1 verification.

## Canonical FULL and optional host fallback

GitHub owns the canonical mapped FULL run. Do not ask the operator to rerun
that same profile locally after a valid green mapped run. The latest successful
comparable baseline on the accepted base is run `45919230088`, with 18,566
passed, 10 skipped, broad-1 at 258.979 seconds, and the slowest lane at
282.020 seconds. The prior broad-1 timing failure at 301.670 seconds remains
preserved; the ceiling is unchanged.

If the mapped CI result is materially host-specific, invalid, or incomplete,
the optional local fallback is the existing FULL runner with the final literal
HEAD/tree substituted after commit and the live feature tracking ref pointing
to that exact source. The exact final command must be returned in the
post-commit handoff. It includes the accepted base, feature branch and tracking
ref, shared Python, canonical F: worktree root, and external temp root. It must
not be run when GitHub has already produced valid canonical FULL evidence for
the same exact source.

PowerShell command shape (fill `<FINAL_HEAD>` and `<FINAL_TREE>` only from the
exact clean committed/pushed source identity):

```powershell
F:\AI\ai-trading-bot\.venv\Scripts\python.exe scripts/run_test_certification.py `
  --profile full `
  --root F:\AI\worktrees\ai-trading-bot-portfolio-manager-current `
  --python F:\AI\ai-trading-bot\.venv\Scripts\python.exe `
  --expected-head <FINAL_HEAD> `
  --expected-tree <FINAL_TREE> `
  --expected-base-head e578a7ff0e128a1f9895a9df82296f73f550e9c5 `
  --expected-branch feature/robinhood-portfolio-manager-current `
  --expected-feature-ref origin/feature/robinhood-portfolio-manager-current `
  --expected-feature-head <FINAL_HEAD> `
  --temp-root F:\AI\temp\pytest
```

The runner creates unique external evidence and lane basetemp paths. A local
fallback still proves only that exact source under the stated host; it does not
replace source admission, GitHub's canonical result, ChatGPT exact-source
acceptance, or any protected/operational gate.
