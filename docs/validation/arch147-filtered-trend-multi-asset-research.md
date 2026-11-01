# Architecture 147 filtered-trend research validation

Source-only checkpoint `arch147-filtered-trend-multi-asset-research` starts from
accepted develop HEAD `6bd95977a17e386bd756ae7bd7b2368ccf1c4e8f`, tree
`df682c11568f4ecf2c3cd03898faa44906d7b296`.
Implementation branch: `feature/research-filtered-trend-multi-asset-current`.
Worktree: `F:\AI\worktrees\ai-trading-bot-filtered-trend-multi-asset-current`.
Contract: [frozen research design](../architecture/147-filtered-trend-multi-asset-research.md).

Focused synthetic tests cover the independent adjusted profile, pagination,
create-only storage, indicator correctness, all 30 candidates' exclusion of
execution-session HLC, warmup, regime resets, allocation/cost accounting,
complete cross-asset summaries, lexicographic ties, canonical bundle tampering,
immutable output and detached reporting. Existing P3/P4/P5A and current authority
regressions remain in the affected checkpoint union. New research test modules
are supported FULL ownership; frozen historical required tuples are unchanged.
The filtered-trend strategy tests explicitly distinguish threshold-only ADX20
(`Wilder ADX(14) >= 20`) from ADX25_RISING (`Wilder ADX(14) >= 25` and current
ADX greater than prior ADX); the canonical Wilder-ADX numeric tests remain
unchanged.

## C2 provider-response compatibility coverage

The C2 correction keeps the multi-symbol response root strict: `bars` and
`next_page_token` are required, `currency` is optional, and every other root
field is rejected. Both legal response shapes are covered: currency absent and
`currency="USD"`. A returned non-USD currency, a non-string currency, an
unrelated root field, and duplicate `currency` JSON keys are rejected. The
request assertion remains frozen at `currency=USD`; this correction adds no
provider, credential, dataset, campaign, holdout, or production effect.
The final focused filtered-trend union passed 115 tests, and the separate
current/routed authority check passed 87 tests.

Prepublication requires the complete focused union, current/routed authority,
historical reconstruction/coherence checks, whole-root combined Ruff/diff,
exact intended-file staging, one normal atomic commit and `ops.ps1 admit`:
FEATURE=PASS, PROSPECTIVE_DEVELOP=PASS, IDENTITY_STABLE=True.
One ordinary push then owns one terminal GitHub FULL attempt; no local canonical
FULL, unchanged rerun, merge or intermediate push. Final identities and actual
results are returned in the implementation handoff; this document does not
claim a future admission or CI result has already occurred.

All fixture bars are synthetic and all acquisition transports injected fakes.
No real Alpaca request, credentials, production dataset, P5 runtime/SQLite/journal,
Robinhood, broker, live effect or FINAL_HOLDOUT read is permitted. Real data
acquisition waits for independent exact-source acceptance/integration and one
separately reviewed operator step. Offline results then stop for strategy review.
