# Validation — Architecture 150 intraday AI day-trading campaign

Status: **FOUNDATION + D1 + D1R + D1R-C1 + D2 SOURCE ACCEPTED/INTEGRATED; SPARSE 2016-2023 CUSTODY ACCEPTED; CANONICAL G1 POPULATION FROZEN IN SOURCE; REAL G1 RESULTS NOT OPENED**.

Normative design:

`../architecture/150-intraday-ai-day-trading-campaign.md`

## Accepted foundation checkpoint

Integrated HEAD: `df504d166690ed7e6d2b67b5376565926b76baed`

Integrated tree: `9431111706710406baf336a7fd6a16f00a8db36a`

Feature mapped FULL: `44975857710`, attempt 1, terminal SUCCESS.

Develop source-gate: `44981797946`, attempt 1, terminal SUCCESS with exact
feature-certification reuse and no duplicate FULL execution.

Route:

`arch150-intraday-ai-research-foundation`

Branch:

`feature/research-arch150-intraday-ai-current`

Worktree:

`F:\AI\worktrees\ai-trading-bot-arch150-intraday-ai-current`

Source-only/fake-only.

## D1 data-custody source checkpoint

Accepted/integrated HEAD:
`55f3bd8ae91c73c15e073c5a13e848f24c919bb9`

Accepted/integrated tree:
`23daa9536fbf73f9c706e5e2661f6b3623dba1d3`

The original D1 publication
`a5bc7ec6bde787490ced14457d7b9bc83ed6e9f4` remains immutable terminal-red
evidence. Mapped run `44990894674`, attempt 1, exposed the test-output-root
portability `PREPUBLICATION_COVERAGE_DEFECT`. Corrective feature run
`44995353037`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven FULL lanes passing. Develop run `44997145175`,
attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`; canonical
FULL was not duplicated.

Route:

`arch150-intraday-data-custody-source`

The source route is separate from the accepted strategy-foundation route and
shares its feature branch. CI selects the route from the exact pushed-commit
path set; mixed foundation and D1 changes fall back to broad FULL routing.

The D1 contract fixes one-symbol requests for SPY then QQQ, `1Min`, the
`[2016-01-01, 2024-01-01)` request window, `adjustment=all`, SIP, USD, ascending
sort, `asof=-`, limit 10,000, exhaustive `next_page_token` pagination, 4,096
pages per symbol / 8,192 requests total, and at least 0.5 seconds between
provider request starts after the first. Each response body is stored
byte-for-byte and read back before page parsing. Raw off-session rows remain in
custody; normalized rows require exact published XNYS one-minute slots, with
early closes respected and no fill, interpolation, or duplicate removal.

Versioned schemas:

- `arch150-intraday-custody-dataset/v1`
- `arch150-intraday-data-partition/v1`
- `arch150-intraday-data-custody-evidence/v1`
- `arch150-intraday-raw-page/v1`
- `arch150-intraday-provider-request/v1`

The accepted interlocked operator writes under
`F:\AI\research-data\arch150-intraday-data-custody`, outside repositories and
worktrees. Its successful state means only that the data custody package is
ready for independent review. It does not open validation for strategy use,
freeze G1, authorize holdout/extension access, or authorize trading. A failed
attempt is immutable and has no automatic retry.

For this source checkpoint, the operator was tested only with injected fake
source facts, credentials, clock, transport, and storage. D1 source review,
feature FULL, fast-forward integration and develop certification reuse were
accepted before the protected effect.

### Consumed real D1 acquisition

The one authorized real attempt is permanently consumed:

- attempt ID: `a8d5975b-a3e9-4917-a8a8-2809e191fa20`;
- retained root:
  `F:\AI\research-data\arch150-intraday-data-custody\arch150-d1-a8d5975b-a3e9-4917-a8a8-2809e191fa20`;
- effect-time source: `50c5ed6204e909534778b07534fee7217117e47e` /
  tree `f53588f74266b3ef054ca49f9ea5c8a29e24d630`;
- outcome: `CONSUMED / BLOCKED / MISSING_EXPECTED_SLOT / NO RETRY`;
- credential reads: 1;
- provider requests/pages: 306;
- SPY: 158 pages, 1,577,355 raw bars, 781,876 observed regular slots,
  104 missing scheduled slots, 0 duplicates, 0 malformed;
- QQQ: 148 pages, 1,474,748 raw bars, 781,865 observed regular slots,
  115 missing scheduled slots, 0 duplicates, 0 malformed;
- both streams: `NULL_TOKEN_EXHAUSTED`;
- dataset identity:
  `6085afed-b870-59d7-9c0d-407db940777b`;
- blocked dataset SHA-256:
  `70bf65d5b5c8726285215ed8337ae06bfaac8371cdb07b5dfd625ed800a96e23`;
- custody evidence identity:
  `c0276e43-7533-5af4-9dbe-bb7e9095e693`;
- byte-level `custody-evidence.json` SHA-256:
  `b83ced21f58cc1aa4731b2e72c1cf8cba4fb7d24378b0f206b303583bc658267`;
- normalized dataset: not produced;
- 2024+ access, strategy P&L, holdout, extension, Robinhood, broker, order and
  production-state effects: all zero.

The attempt is immutable. Do not reacquire, resume, regenerate or overwrite it.

### D1R offline sparse-custody requalification

D1R source is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at:

- HEAD: `fd0eb9073d55cbb5b1dba2f0fb35ce00317855c1`;
- tree: `bec66738a1796a0300b1dd5bbd503675203eb506`;
- direct parent: `f376f10840ab40723af6393b9918fab67702a073`;
- feature mapped FULL: `45012246733`, attempt 1, terminal SUCCESS with
  source-static, active-tests, source-gates and all seven canonical FULL lanes
  passing;
- develop run: `45015293875`, attempt 1, terminal SUCCESS with
  `DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`,
  `IDENTITY_STABLE=True`, `OVERALL=PASS`, and no duplicate FULL.

The accepted source checkpoint:

- pin the consumed attempt ID, source identity, artifact hashes, page counts,
  raw counts, request descriptors and null-token exhaustion;
- re-read every raw page read-only and verify byte/hash identity before parsing;
- reuse the accepted D1 parser and published XNYS schedule;
- reject any wrong symbol, duplicate, reordered, malformed, off-grid
  regular-session bar, page/token-chain mismatch, artifact drift, reparse/path
  alias or unexpected attempt content;
- build a new versioned sparse custody dataset/evidence identity without
  mutating the original dense dataset;
- record per-symbol scheduled/observed/missing counts and missing digests,
  common/union missing sets, affected-session diagnostics, discovery/validation
  partition facts, and all zero-effect counters;
- write fresh create-once requalification artifacts outside the consumed
  attempt and outside repositories/worktrees;
- expose no strategy replay or P&L path.

The first real D1R offline invocation is now consumed:

- requested output:
  `F:\AI\temp\arch150-d1r-offline-requalification-e8040deb-1fb6-4a4d-9ac6-05f5c4f6349d`;
- outcome: `CONSUMED / BLOCKED / OUTPUT_CREATE_FAILED / NO AUTOMATIC RETRY`;
- Python exit code: 21;
- no sparse classification or output artifacts were produced;
- the requested output directory does not exist and there is no partial output;
- all retained D1 top-level artifact hashes and raw page filename counts remained
  unchanged;
- new credential/provider/Robinhood/broker/order/strategy-P&L/holdout/extension
  effects: zero.

The sanitized observation does not prove the exact host exception and must not
be retried unchanged. Exact-source review identified a bounded output-boundary
defect class that must be corrected before any later invocation: D1R validates a
normalized absolute output path but writes using the caller's original Path
object, does not explicitly reject control characters, and exposes no CLI path
boundary to avoid Python string-literal escaping on Windows. This is a
source-only correction checkpoint; it must use synthetic tests and perform no
read of the real consumed D1 attempt.

D1R-C1 output-boundary correction is SOURCE/CERTIFICATION ACCEPTED and
FAST-FORWARD INTEGRATED at:

- HEAD: `3afcc5b24845c6ed4e50dd4bbfe34d9deb076d5d`;
- tree: `f393498786060a6e55eed545f6fdd44ecea49f4d`;
- direct parent: `b769a3a5565bdbda18b0fd2ff76eadbd7b1f6071`;
- feature mapped FULL: `45087988867`, attempt 1, terminal SUCCESS with
  source-static, active-tests, source-gates and all seven canonical FULL lanes
  passing;
- develop run: `45100486575`, attempt 1, terminal SUCCESS with
  `DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`,
  `IDENTITY_STABLE=True`, `OVERALL=PASS`, and no duplicate FULL.

The correction canonicalizes the validated output path once and uses that exact
Path for write/result, rejects control characters before any create attempt,
and exposes a CLI boundary:

`python -B -m trading_bot.experiments.arch150_d1_requalify --output-directory <output-directory>`

The corrected real offline D1R observation is now CONSUMED and independently
accepted as sparse custody READY:

- output:
  `F:\AI\temp\arch150-d1r-offline-requalification-a46c4ad1-4287-4e51-8741-0316f784f1de`;
- classification:
  `OFFLINE_SPARSE_CUSTODY_READY_FOR_INDEPENDENT_REVIEW`;
- dataset identity / semantic SHA-256:
  `ff5a3847-09c2-5902-b174-9e77eebf7d53` /
  `0070a5c0cfa5cd7878253d93bc0895b46da28d8b5e2a71395e66ce904b3f85dd`;
- custody identity / semantic SHA-256:
  `21e121dc-a9da-538f-bc88-c15fe7ea7f50` /
  `5b6ac554eda73b588f2f6d664c14e5c7fca3c151966cb546c17621d0c7e6ad83`;
- evidence identity / semantic SHA-256:
  `c31bb29d-3d53-5e2f-a01f-55a42ec96295` /
  `e58a6e5d95c44b33eb34311f705e6cc26982120689f98ddb207768dc304b4ecd`;
- scheduled slots per symbol: 781,980;
- SPY: 781,876 observed / 104 missing;
- QQQ: 781,865 observed / 115 missing;
- common missing: 64; union missing: 155;
- affected sessions: 9; fully missing sessions: 0 for both symbols;
- sessions affected in both symbols: 5;
- per-session commitment records: 2,012;
- duplicates/malformed: 0 for both symbols;
- both pagination streams: `NULL_TOKEN_EXHAUSTED`;
- discovery/validation counts reconcile exactly to each symbol's observed total;
- all new credential/network/provider/Robinhood/broker/order/strategy-P&L/
  holdout/extension/production-state effect counters: zero;
- the immutable original D1 attempt and failed first D1R observation remain
  unchanged.

The sparse evidence is internally consistent:
`781876 + 104 = 781980`, `781865 + 115 = 781980`, and
`104 + 115 - 64 = 155`. The accepted contract intentionally uses no
post-result numeric missing-count threshold; missing minutes remain explicit
absence and no OHLCV was synthesized.

Sparse custody acceptance does not itself authorize strategy P&L. D2
sparse-replay semantics are SOURCE/CERTIFICATION ACCEPTED and integrated at
HEAD `6fb7b128d83b4846b384bb1709f0ee4e724d173d` / tree
`7fd5ea4c516a7f97ce2f5227befd4dbef4e3a802`. Feature FULL run `45113622952`,
attempt 1, is terminal SUCCESS. Develop run `45122666587`, attempt 1, is
terminal SUCCESS with exact feature-certification reuse; no duplicate FULL ran.

## Canonical G1 population freeze

The source-owned canonical manifest is frozen before any real strategy result
is visible:

- schema: `arch150-g1-pre-evaluation-population/v2`;
- manifest ID: `7e179cbc-18cf-59ce-9116-899cc876ece0`;
- 24 ordered slots, eight per family;
- 12 SPY and 12 QQQ slots, all `ONE_MINUTE`;
- each slot identity binds the typed program semantic fingerprint, source symbol,
  and bar resolution.

The canonical order is four variants per family, with SPY followed by QQQ for
each variant:

| Slots | Family and structural variant | Frozen parameters |
| --- | --- | --- |
| 1–2 | A1 noise-area/VWAP momentum | lookback 3 sessions; noise band 10 bps; 1 confirmation bar; 15-minute max hold |
| 3–4 | A2 noise-area/VWAP momentum | lookback 5; 20 bps; 2 confirmation bars; 30-minute max hold |
| 5–6 | A3 noise-area/VWAP momentum | lookback 10; 35 bps; 2 confirmation bars; 45-minute max hold |
| 7–8 | A4 noise-area/VWAP momentum | lookback 20; 50 bps; 3 confirmation bars; 60-minute max hold |
| 9–10 | B1 VWAP continuation above | displacement 10 bps; 1 confirmation bar; 15-minute max hold; 5-bar cooldown |
| 11–12 | B2 VWAP continuation below | displacement 10 bps; 1 confirmation bar; 15-minute max hold; 5-bar cooldown |
| 13–14 | B3 bounded reversal above | displacement 35 bps; 2 confirmation bars; 20-minute max hold; 10-bar cooldown |
| 15–16 | B4 bounded reversal below | displacement 35 bps; 2 confirmation bars; 20-minute max hold; 10-bar cooldown |
| 17–18 | C1 opening-range continuation | 5-minute range; no entry delay; 10-minute max hold |
| 19–20 | C2 opening-range continuation | 15-minute range; 1-bar entry delay; 20-minute max hold |
| 21–22 | C3 opening-range reversal | 15-minute range; 1-bar entry delay; 20-minute max hold |
| 23–24 | C4 opening-range reversal | 30-minute range; 2-bar entry delay; 30-minute max hold |

Within every row above, the odd-numbered slot is SPY and the next slot is QQQ.
All slots use `BarResolution.ONE_MINUTE`. The same program on the two symbols is
two distinct trial identities; a repeated program/symbol/resolution in a
synthetic population is a duplicate. Five-minute G1 trials are not permitted.
The official evaluator accepts only the source-owned canonical manifest and
derives symbol/resolution from each frozen slot.

The discovery advancement rule is frozen: INVALID, DUPLICATE, deterministic
FAILED, and ZERO_TRADE retain their terminal dispositions. Each valid unique
trial that produces at least one STRESS discovery trade becomes SHORTLISTED.
Return magnitude, Sharpe, win rate, profit factor, BASE, and ZERO do not decide
advancement. BASE and ZERO are diagnostics only; validation is the first
economic/frequency rejection stage.

No real G1 trial has been consumed, no real sparse custody file was read for
strategy evaluation, and no strategy P&L was generated. Validation
`[2021-01-01, 2024-01-01)` remains unopened. 2024+ remains sealed.

## Initial implementation scope

Implement:

- typed intraday program grammar for the three frozen families;
- deterministic ordered G1 proposal manifest frozen before evaluation, with an
  opened-discovery, slot-bound evaluator and immutable terminal trial ledger;
- post-discovery finalization and candidate authorization bound to the complete
  manifest, result ledger, and discovery dataset;
- deterministic session-flat replay interface;
- BASE/STRESS/zero-friction cost contracts;
- frequency diagnostics;
- validation ranking data model;
- selection-bias input schema;
- discovery/validation/holdout/recent-extension information-firewall types;
- source-gate route/profile registration;
- synthetic tests.

Do not open real intraday market data in the foundation checkpoint.

## Data acquisition sequence

After foundation acceptance, the source/evidence sequence is:

1. acquire and preserve only SPY/QQQ 1-minute discovery+validation data for
   `[2016-01-01, 2024-01-01)`;
2. validate/custody that dataset;
3. accept D2 sparse-replay semantics;
4. freeze the complete canonical G1 population before P&L visibility;
5. run the separately reviewed one-shot 2016-2020 G1 discovery evaluation;
6. only after discovery is terminal, open 2021-2023 validation;
7. perform selection-bias correction and freeze final candidate set;
8. only then acquire/open 2024-2025 holdout data;
9. if a candidate survives, only then acquire/open the fixed Jan-Oct 2026
   recent-regime extension.

No waiting for the end of calendar 2026 is required.

## Synthetic source tests

Pin at minimum:

- exact SPY/QQQ universe;
- regular-session-only bars;
- session-flat invariant;
- no overnight carry;
- no pyramiding/martingale/averaging-down;
- at most three median trades per active session for advancing candidates;
- active-session and annual trade-frequency diagnostics;
- at most 24 frozen G1 trial slots / at most 8 per family, including valid and
  explicit invalid proposals;
- nonempty ordered manifest identity is deterministic and preserves duplicate
  proposal slots;
- every official evaluation consumes only the next exact frozen slot;
- invalid, duplicate, zero-trade, deterministic-failure, and shortlist results
  all consume their frozen trial slot;
- each canonical trial binds its program, SPY/QQQ source symbol, and one-minute
  resolution in manifest, evaluation, ledger, candidate, and selection-bias
  identities;
- a same-program SPY/QQQ pair has distinct trial identities, while repeating
  the exact program/symbol/resolution is a duplicate;
- every valid unique STRESS discovery replay with a trade is shortlisted;
  discovery economics and BASE/ZERO diagnostics cannot reject or promote;
- BASE 2-bps/fill and STRESS 5-bps/fill contracts;
- zero-friction cannot qualify;
- complete-trial-ledger DSR/multiple-testing inputs;
- 2016-2020 discovery boundary;
- 2021-2023 validation boundary;
- 2024-2025 holdout firewall;
- Jan-Oct 2026 extension firewall;
- rejected Architecture-148 opening-drive rule excluded;
- Architecture-149 source/evidence untouched;
- zero provider/credential/Robinhood/broker/order/production/FINAL_HOLDOUT
  effects.

Use focused pytest with `-p no:cacheprovider` and unique external basetemp.

Do not run local FULL unless repository admission requires it.

Publication is one atomic commit, one ordinary push, one mapped CI run.

Future Architecture-150 implementation follows the current workflow routing.
For delegated implementation, one implementing Codex session owns focused test
results and its mapped GitHub CI through terminal, including fully reproduced
bounded/mechanical corrective descendants. Do not create a separate coordinator,
subagent, or waiting/polling agent unless explicitly requested.
