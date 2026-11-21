# AI Trading Bot - Project Status

## Current milestone - Architecture 150 intraday AI day-trading campaign frozen; foundation next

Architecture 148-B2-A-C1 is **SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD
INTEGRATED** at HEAD `0ebeaef7ea8ee83677d775fe66d037efa76c8cf1` / tree
`e16fe3aeec6a862c0d7ad7dd35e4171c1d3385e7`, direct parent
`298bba38cf61d506fec68cb7034fc66a58218078`. Feature source-gate
`44507842755`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven mapped canonical FULL lanes passing. Develop
source-gate `44616906540`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True`, reason `exact_feature_certification`, and
`IDENTITY_STABLE=True`; active-tests, full-tests, certification-tests and
certification-full were skipped, so no duplicate FULL ran. The local integration
checkout was then proved clean at the exact accepted HEAD/tree.

Dashboard: B2-B attempt `fd8aa437-c748-4d5b-a52f-1e58b2ca5953` at
`F:\AI\temp\arch148-b2-fd8aa437-c748-4d5b-a52f-1e58b2ca5953` remains
CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO RETRY. Credential reads: 1;
provider attempts/pages: 64/64; QQQ raw/regular-slot/off-slot bars: 162426 /
78057 / 84369; unresolved intent: NONE; Robinhood/broker/order/production/
FINAL_HOLDOUT/baseline effects: 0. The immutable attempt cannot be retried.

Later attempt `bb1a784b-98d1-41fd-8d95-aa9fa463d5c9` at
`F:\AI\temp\arch148-b2-bb1a784b-98d1-41fd-8d95-aa9fa463d5c9` completed
acquisition with 1 credential read, 430/430 pages, 0 unresolved pagination
intents, and null end cursors for all three symbols. The preserved data failed
the original dense B1 downstream qualification:
QQQ 148 pages / 349805 raw / 156379 observed / 17 missing;
TQQQ 141 / 331112 / 156376 / 20 missing;
SQQQ 141 / 328679 / 156376 / 20 missing. The missing-slot sets share 17
timestamps and have a 23-timestamp union. This attempt is CONSUMED / BLOCKED /
`QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY. It remains separate from the
older fd8aa page-limit incident.

B2-A-C1 preserves B1 and now implements validated raw-to-B1 exact-slot
projection, v2 per-symbol raw/qualified/excluded evidence counts, ceilings of
192 pages per symbol and 576 total attempts, and 0.5-second minimum pacing
between provider-request starts after the first. C1 source work, certification
and integration performed zero credential/provider, Robinhood, broker, order,
production, baseline or FINAL_HOLDOUT effects.

`ARCH148_B2_A_C1_TRANSITION_NATIVE_STDERR_REGRESSION` records one integration
wrapper defect: the local fast-forward and `git push origin develop` both
succeeded, but the wrapper combined `$ErrorActionPreference='Stop'` with native
stderr redirection and converted Git's normal remote-status stderr into a
terminating `NativeCommandError` before the final verification prints. GitHub
then proved both remote refs at the accepted SHA, develop CI ran normally, and
a separate read-only local proof established the clean integrated HEAD/tree.
No duplicate push/merge or source/protected effect occurred. Existing workflow
rules already prohibit this stderr-unsafe pattern; no workflow-source change is
needed.

The Architecture 148 public-reference completion wave is independently
SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD
`6fb78af8c2e07d906629fd95277343eb6d54fde3` / tree
`01091cea96aa3aba6e5de8b88b64d8f722f116ba`, direct parent
`e11840c2ec7054c79183b3e33aee032f427d1a69`. Feature mapped FULL run
`44673337558`, attempt 1, is terminal SUCCESS; develop run
`44679168920`, attempt 1, is terminal SUCCESS on the exact accepted SHA.

The offline requalification of immutable `bb1a...` raw acquisition evidence is
independently ACCEPTED. Evidence:
`F:\AI\temp\arch148-b2-offline-requalification-b9a8babd-4869-466d-a81f-fae08fe2aae5\evidence.json`,
65,688 bytes, SHA-256
`bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`.
It binds dataset identity `0308b694-c718-5b1a-a51c-9fcc4516bb81` /
SHA-256 `0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0`
and custody identity `dbcced6a-b4cc-5d36-a33b-5e6df3d82baa` /
SHA-256 `93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b`.
Observed regular-session bars are QQQ 156379, TQQQ 156376 and SQQQ 156376;
missing counts are 17/20/20 with 17 common and 23 union missing slots and zero
fully missing expected sessions. Requalification performed zero credential,
network/provider, Robinhood/broker, order, production-state, FINAL_HOLDOUT or
baseline effects. The consumed `bb1a...` acquisition remains immutable and NO
RETRY.

[Architecture 148 churn research](validation/arch148-churn-research.md) is
independently SOURCE/CERTIFICATION/EVIDENCE ACCEPTED and FAST-FORWARD
INTEGRATED at HEAD `be30617594e197f372438dba19d325fd8737b850` / tree
`57d5e80bd1933d59faf5da07f0ea293eac34b323`, direct parent
`0e82457d71e584dc526b5e377d7f90867e515879`. Feature mapped FULL run
`44695628477`, attempt 1, is terminal SUCCESS with source-static,
active-tests, source-gates and all seven canonical FULL lanes passing. Develop
run `44698088183`, attempt 1, is terminal SUCCESS on the exact integrated SHA;
source-static and source-gates passed while active/FULL/certification execution
was skipped, so no duplicate FULL ran.

Accepted OPEN research evidence is
`F:\AI\temp\arch148-churn-research-731f1ee4-53a1-4bdf-8979-5eef493d9f4a\research.json`,
299,259 bytes, identity `19dcca18-7080-541d-9864-d730c68471e0`, SHA-256
`5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8`.
It binds the accepted sparse dataset/custody/requalification/baseline inputs,
all four frozen variants, both cost models and nine OPEN partitions per run.
CONTROL reproduced the accepted baseline. Opposite confirmation roughly halved
trade count, but CONTROL, opposite confirmation, 15-minute cooldown and
30-minute cooldown are all economically REJECTED: every variant lost money in
every 2016-2023 calendar-year OPEN slice at `CONSERVATIVE_10_BPS`; the best
descriptive result, 30-minute cooldown, still returned about `-99.4027%`
across OPEN. No variant was selected. `FINAL_HOLDOUT` remained sealed and all
recorded credential/network/provider/Robinhood/broker/order/production effects
were zero. Live promotion still requires a viable strategy plus the existing
provider-scope, whole-share stop, approval-linkage and risk/notional blockers.

The active research roadmap is the
[AI Strategy Discovery Campaign v1](validation/ai-strategy-discovery-campaign-v1.md).

Generation 0 is accepted. Generation 1 consumed the exact frozen 22-program
daily multi-asset population once over the 2019-2021 discovery partition.
Accepted G1 identities are proposal set
`b2b3cadc-c11d-5a7a-be0b-5a2e16b9b39b`, batch
`fd53330e-82ff-58a3-99b8-1818b9a0bbc0`, analysis
`d5ca081e-7490-5590-921d-10cee373d012` and terminal ledger
`68418f44-7db0-5080-a6bd-a956a928bd4a`. G1 consumed 22 trials:
12 SHORTLISTED and 10 ECONOMICALLY_REJECTED. Its immutable evidence remains at
`F:\AI\temp\ai-strategy-discovery-g1-run-fd53330e-82ff-58a3-99b8-1818b9a0bbc0`
and must not be regenerated or overwritten.

Generation 2 is also consumed and must not be rerun or mutated using visible
confirmation results. Its proposal set is
`c958130d-7594-535b-aa46-065525a10c46`, batch
`8c85731c-75dd-5a60-9456-10f237a6b0dd`, analysis
`821697c8-9917-5b76-b519-f81a2452d7f6` and terminal ledger
`e86be80c-562c-5243-bc56-9e4a9e4c9f6d`. It consumed six G2 trials:
0 CONFIRMATION_PASSED and 6 CONFIRMATION_REJECTED. The frozen momentum-admission
recombination hypothesis is rejected. Total campaign evaluated trials are 28.
The G2 evidence root is
`F:\AI\temp\ai-strategy-discovery-g2-run-8c85731c-75dd-5a60-9456-10f237a6b0dd`.
`FINAL_HOLDOUT` remains sealed.

The G1 selection-bias source checkpoint is independently
SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD
`c26315b37c9b5fce355f323484f639368ce95749` / tree
`b3c678459062d24ae67f901b40cf7bc496ea6b87`, direct parent
`170790fb60615e57c26e6a6c073834d4c94bb03a`. Feature mapped FULL run
`44881687514`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven mapped FULL lanes passing. Develop run
`44882606523`, attempt 1, is terminal SUCCESS with exact feature-certification
reuse; active/FULL/certification execution was skipped, so no duplicate FULL ran.

The accepted source reconstructs all 176 continuous stress equity traces from
the accepted G1 fills and adjusted closes without replaying strategy signals,
requires exact accepted equity-trace identities, builds one equal-weight
eight-sleeve daily return series for each of all 22 G1 programs, and applies the
frozen 22-trial Deflated Sharpe Ratio plus the separately labeled
28-trial Bonferroni PSR sensitivity. Only the 12 original G1 shortlists were
eligible for SELECTION_BIAS_PASSED/REJECTED.

The real selection-bias observation is CONSUMED at source
`d68672d998b059d677fdc0a05e225a3c9689c1fc` / tree
`a771f9d51e6fa3570071b237756ba6d3141a78bb`. Report identity
`854a1c95-f236-5dd7-9706-41035dd7fdf7`, SHA-256
`99e407ea3f646ecdd3ce17d9652356b1d0ee40bc0504d639841d2fcffd8bd708`,
is preserved at
`F:\AI\temp\ai-strategy-discovery-selection-bias-854a1c95-f236-5dd7-9706-41035dd7fdf7\selection-bias.json`.
All 12 eligible G1 shortlists were SELECTION_BIAS_REJECTED; zero passed. The
best shortlisted DSR was about 0.918051, below the frozen 0.95 threshold, and
its one-sided campaign PSR p-value was about 0.0139583 versus
`0.05 / 28 = 0.001785714...`. No walk-forward candidate survives this daily
campaign. The observation added zero new strategy trials, replayed no strategy,
read no G2 artifact, performed zero provider/broker/production effects, and
kept `FINAL_HOLDOUT` sealed. Do not tune, mutate, rerun, or reopen this daily
branch using the visible G1/G2/DSR results.

The Architecture 148 late-session intraday-momentum source checkpoint for
`OPENING_DRIVE_LATE_CAPTURE_V1` is independently SOURCE/CERTIFICATION ACCEPTED
and FAST-FORWARD INTEGRATED at HEAD
`370ebccf52a61e91979bc61efaac0001dd563be6` / tree
`49dbdc10401203422d5f8af7d4a936d9cd92a7f3`, direct parent
`92affe94d076b6035ad7e511ef7625335127f5e3`. Feature mapped FULL run
`44888198054`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven mapped FULL lanes passing. Develop run
`44889299328`, attempt 1, is terminal SUCCESS with exact feature-certification
reuse; active/FULL/certification execution was skipped, so no duplicate FULL
ran.

The source preserves exactly one frozen candidate, explicit XNYS authority,
previous-close/first-half-hour direction, close-minus-35-minute scheduled entry,
one-entry-per-session, the existing 3% stop/safety/forced-flat semantics, and
the two accepted cost cases. The preserved QQQ data-readiness veto is recorded
separately from strategy eligibility and was frozen before real results.

The one-shot real OPEN observation is CONSUMED and terminally
`ECONOMICALLY_REJECTED`. Report identity
`42355698-d57e-5f6b-8347-6a752e5b4572`, SHA-256
`e6349ea0c7f1e1b09f165bede8c93b68fb6bc6168940fda0ae2270bf9079f19b`,
is preserved at
`F:\AI\temp\arch148-intraday-momentum-research-42355698-d57e-5f6b-8347-6a752e5b4572\research.json`.
ZERO_COST OPEN_FULL returned about +24.96%, but CONSERVATIVE_10_BPS returned
about -97.65%; the median conservative annual return was about -39.86%, with
only 2020 positive among the eight calendar-year partitions. The opening-drive
direction hit rate was about 49.48%, and both TQQQ and SQQQ realized mean
returns were negative under conservative costs. No confirmation/holdout step is
authorized. Do not tune, threshold, retime, rerun or mutate this hypothesis from
its now-visible P&L.

The observation performed zero credential/network/provider/Robinhood/broker/
order/production effects, zero baseline replay, and zero `FINAL_HOLDOUT`
access. `FINAL_HOLDOUT` remains sealed. No earlier frozen unevaluated trading hypothesis remained after that closeout.
Architecture 149 remains a valid preserved secondary benchmark, but it no
longer blocks the primary bot roadmap. Its exploratory result and frozen
2024-2026 confirmation contract remain immutable; confirmation may be resumed
later as a low-turnover benchmark.

The primary product roadmap is now
[Architecture 150 intraday AI day-trading campaign](architecture/150-intraday-ai-day-trading-campaign.md).
It targets frequent same-day opportunities on SPY/QQQ, mandatory end-of-session
flatness, bounded AI-generated deterministic intraday programs, realistic
per-fill costs, full trial-ledger selection-bias correction, an untouched
2024-2025 historical holdout, and a fixed Jan-Oct 2026 recent-regime extension.
This uses completed historical periods available now and does not require
waiting for calendar year-end. The foundation source is NOT IMPLEMENTED and no
Architecture-150 real data has been opened.

Architecture 149 now owns the next independent strategy family:
`MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1`. It is a single low-turnover,
monthly cross-asset relative-strength rule over the accepted eight-ETF A147
universe, with a strict positive-momentum-to-ETF / nonpositive-to-CASH gate and
no parameter grid. 2016 is warmup; 2017-2023 is exploratory evidence only.
2024-2026 data remains outside the current input boundary and may be acquired
only after a surviving exploratory result and a separately frozen confirmation
contract.

The Architecture-149 source checkpoint is independently
SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD
`57087af056767c59ee48e3edb86063ac4f20c10d` / tree
`da80c3f560d54d959822f7716a50fc45c3ead716`, direct parent
`088f5aa4581bcb2b211c69f71f447ab9cb98e645`. Feature mapped FULL run
`44914956812`, attempt 1, is terminal SUCCESS with source-static, active-tests,
source-gates and all seven FULL lanes passing. Develop run
`44935678418`, attempt 1, is terminal SUCCESS with exact feature-certification
reuse and no duplicate FULL.

The accepted evaluator binds the exact A147 dataset identity and canonical
SHA-256 before replay, physically rejects post-2023 bars, retains December 2023
as a terminal non-executable target without a 2024 lookup, and implements one
continuous $100,000 BASE/STRESS portfolio path.

The one authorized 2017-2023 exploratory replay is CONSUMED and classified
`EXPLORATORY_CANDIDATE_ONLY`. Report identity
`8a3d7c3a-d2f9-5f10-91e6-ba06c3935d84`, SHA-256
`69f941721aaba736cef45b80543f7a238a30dcdb74f03c046c3fc01aabb5dbcf`,
is preserved at
`F:\AI\temp\arch149-monthly-defensive-rotation-8a3d7c3a-d2f9-5f10-91e6-ba06c3935d84\research.json`.
Under STRESS it returned about +82.59% across 2017-2023, CAGR about 8.98%,
maximum drawdown about 28.15%, Sharpe about 0.5183, median annual return about
10.86%, and six of seven calendar years positive. The result consumed exactly
one Architecture-149 strategy trial and performed zero provider/broker/
production/FINAL_HOLDOUT effects.

The 2024-2026 confirmation contract is now frozen before any confirmation data
is opened. Partial 2026 or year-to-date confirmation is forbidden. Source-only
confirmation support is the next implementation milestone; real confirmation
data acquisition/replay must wait until calendar 2026 is complete.
See
[Architecture 149](architecture/149-monthly-cross-asset-defensive-rotation.md)
and its
[validation plan](validation/arch149-monthly-cross-asset-defensive-rotation.md).

The previously frozen OPEN-only design remains in
[Architecture 148 late-session intraday momentum research](validation/arch148-intraday-momentum-research.md).
It is a materially different entry/holding architecture, not another churn
threshold: QQQ's first-half-hour return from the previous regular-session
close supplies one direction for the day; the strategy may make at most one
scheduled TQQQ/SQQQ entry at official close minus 35 minutes and then holds
until the existing 3% hard stop, a safety exit, or the existing forced-flat
boundary at close minus 5 minutes. EMA/VWAP/RSI regime flips, cooldowns and
same-session re-entry are not part of this candidate. The design uses only
the accepted sparse OPEN dataset, both accepted cost cases and the existing
2016-2023 reporting partitions. Executable source is now accepted/integrated;
no real OPEN result is claimed yet. `FINAL_HOLDOUT` remains sealed and all provider/broker
boundaries remain unchanged.

The accepted sparse OPEN baseline remains unchanged at
`F:\AI\temp\arch148-open-sparse-baseline-e3e27c29-8a9d-41c5-9ac0-d89a1d4cb5d1\baseline.json`,
SHA-256 `38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f`.
It records 6,233 `ZERO_COST` and 6,235 `CONSERVATIVE_10_BPS` trades, 5,446 and
5,439 regime exits respectively, and `-99.998648%` conservative return. The
baseline economics are rejected; these values are not churn results.

Architecture 148 is now the current product direction under [the frozen pivot design](architecture/148-tqqq-sqqq-runtime-pivot.md). The canonical pinned source/runtime/public-reference map is [the 148 parity matrix](validation/arch148-runtime-parity.md); it records local source/tests, external licenses, adopted behavior and intentional exclusions, and grants no provider authority. The first application version is intraday-only and may hold exactly one of TQQQ, SQQQ or FLAT. QQQ is the primary direction reference. V1 uses completed 5-minute bars, session VWAP, EMA(20), EMA(50) and RSI(14), requires two consecutive same-direction completed bars before an entry, forbids same-cycle flips, and forces the application flat beginning five minutes before the official regular-session close.

The hard stop-loss invariant is source-owned at 3.00% below the reconciled average entry fill and may never be widened. A broker-resident full-position stop-market order is the preferred live protection; software logic independently treats a stop breach as mandatory EXIT. Live promotion is blocked when exact full-position stop protection cannot be proven. Whole-share entry sizing uses a fresh price, cash, unleveraged buying power and existing risk controls while retaining the <=$10 acquisition ceiling. A quantity-denominated market order has no capped fill price and does not guarantee a <=$10 fill. Robinhood's stop execution price is also not guaranteed, so the stop is an exit/protection invariant rather than a guaranteed maximum loss.

Architecture 148 adopts the simple application-loop shape reviewed in `siropkin/robinhood-ai-trading-bot@1a778749cfbe92c7ab9444b12e3cc73587533ade` while retaining this repository's stronger MCP OAuth/session, deterministic risk, durable intent, `ref_id`, UNKNOWN/no-retry reconciliation, source/state continuity, XNYS calendar, research/backtest, GUI and certification components. Direct Robinhood username/password login, `robin_stocks`, generic write retry and prompt-only risk constraints are explicitly not adopted.

Architecture 148-A is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd` / tree `2e139bdd886ee6ce8f92da57cc11ea38f341114f`, direct parent `ec0f33b7c15521c1901d749d5a933564360448c7`. Feature mapped FULL run `44411012023`, attempt 1, is terminal SUCCESS with source-static, active-tests, all seven canonical FULL lanes and source-gates green. Develop run `44423510835`, attempt 1, is terminal SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, reason `exact_feature_certification`, `IDENTITY_STABLE=True`, and no duplicate FULL.

Independent exact-source review accepted the effect-free `live_runtime` skeleton, its completed-bar QQQ regime classifier, XNYS entry/forced-flat policy, 3% hard-stop invariant, deterministic intent/`ref_id`, exact review/admission binding, UNKNOWN/no-retry reconciliation and protective-stop lifecycle model. No real Robinhood/OAuth/browser/Alpaca/review/place/cancel or production-state preparation occurred. Two live-promotion blockers remain intentionally explicit rather than bypassed: current MCP stop-market protection is whole-share constrained relative to the retained <=$10 tiny-live authority, and approval-originated orders can require provider approval-ID linkage instead of the original `ref_id`.

`ARCH148_A_CONNECTOR_INTEGRATION_MECHANISM_DEVIATION` records that ChatGPT performed the accepted strict-descendant integration with a non-force expected-old-SHA GitHub ref fast-forward because this review turn was constrained to the GitHub connector, rather than the repository-preferred admitted local `git merge --ff-only` plus ordinary push. The resulting remote history is still the exact accepted one-parent SHA/tree and develop certification reuse passed; this mechanism is not promoted as the normal integration procedure.

Architecture 148-B1 is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD `68b9526f022458cbcdd4f25ff268e0de7c56e562` / tree `85e4830e71cb3b0ab5e85c5da9131f90f7ce575b`. The initial B1 source commit `70b0a8de5cb3b2cf4fb826352b6ada3650c57614` and mapped run `44432367772` remain preserved; exact-source review rejected that source for the historical-session schedule, entry-bar stop simulation and schedule-provenance binding defects. Corrective C1 `68b9526f022458cbcdd4f25ff268e0de7c56e562` closed those defects and mapped feature FULL run `44438409583`, attempt 1, is terminal SUCCESS. Develop run `44465681331`, attempt 1, is terminal SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, reason `exact_feature_certification`, `IDENTITY_STABLE=True`, and no duplicate FULL lanes.

The accepted B1 OPEN contract is completed 5-minute QQQ/TQQQ/SQQQ research data over `[2016-01-01, 2024-01-01)` UTC with `adjustment=all`, SIP, USD and price basis `ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1`. Architecture 148 owns the separately committed intraday schedule identity `4fe981d0-34ef-57be-a7d1-ffd017460bf5` / SHA-256 `a33be70499cdafbfa21f45a04c854ab834425807b6c0314814b7442749aa2bad`. The simulator preserves completed-bar no-lookahead entry, conservative immediate entry-bar hard-stop handling, shared regime-exit semantics and deterministic fake-only controls. No real provider, credential, Robinhood, broker, production-state or `FINAL_HOLDOUT` effect occurred during B1.

The earlier B2-B attempt remains CONSUMED / BLOCKED / PAGE_LIMIT_REACHED / NO
RETRY. The later `bb1a...` acquisition remains CONSUMED / BLOCKED /
`QUALIFICATION_BAR_COUNT_MISMATCH` / NO RETRY under the original dense B1
contract. B2-A-C1 remains accepted/integrated at
`0ebeaef7ea8ee83677d775fe66d037efa76c8cf1` /
`e16fe3aeec6a862c0d7ad7dd35e4171c1d3385e7`. Its immutable raw observations
are independently accepted through the sparse offline requalification evidence
recorded above; no provider retry is authorized. The accepted churn study uses
that sparse source and baseline as fixed inputs and preserves the independently
accepted OPEN evidence/hash recorded above. All four tested variants remain
economically rejected and `FINAL_HOLDOUT` remains sealed.
Q1 remains CONSUMED / BLOCKED / NO AUTOMATIC RETRY; Q63 remains NOT RUN and
`FINAL_HOLDOUT` remains SEALED.

L43-Q1 source/certification is independently ACCEPTED and FAST-FORWARD INTEGRATED at HEAD `05f4c4700f82c3d40c83f474c3cf614573d48091` / tree `70aec1c51e63705a68d6710cc3448ac994227e46`. Feature mapped FULL run `44260469616`, attempt 1, is terminal SUCCESS with source-static, active-tests, source-gates and all seven canonical FULL lanes passing. Develop run `44264566809`, attempt 1, is terminal SUCCESS with exact feature-certification reuse; active/FULL/certification jobs were skipped on develop, so no duplicate FULL ran. Local feature/develop reconciliation later reached the same exact clean HEAD/tree.

The first separately reviewed real Q1 protected read-only preflight is CONSUMED / BLOCKED / NO AUTOMATIC RETRY. Evidence is `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch147-l43-qualification-preflight\\preflight-20261118T091033.372793Z\\report.json`. Source admission passed before and after on the exact accepted HEAD/tree with `IDENTITY_STABLE=True`; the qualification result was `BLOCKED / QUALIFICATION_INDETERMINATE`. It bound the accepted source plus Q62 config/binding/journal digests, but no L43 durable-state snapshot or fresh pre-effect/provider facts were captured. Review, placement, cancellation, broker mutation, L43 durable-state mutation and Q62 journal mutation counters were all zero. Provider-read/credential counters are `null`, meaning unknown rather than zero; the result does not prove any provider call occurred.

RHC4-C2 is independently SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at HEAD `4f560a74b04ecba85c7b312364a9e4e7b30e57b6` / tree `b422ef66d88b184bdbe12788546e6b2ffd083846`. Feature mapped FULL run `44217082229`, attempt 1, is terminal SUCCESS with source-static, active-tests, source-gates and all seven canonical FULL lanes passing. Develop run `44236195177`, attempt 1, is terminal SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, reason `exact_feature_certification`, and `IDENTITY_STABLE=True`; active tests and FULL were skipped on develop, so `DEVELOP_DUPLICATE_FULL=NO`.

The accepted RHC4 runtime composes the canonical Q62/RHC3 read authority, RHC3P repeatable settlement, durable L43 state owner, current Robinhood transport, Alpaca runtime signal and the L43 effect operator behind one explicit restricted-live application path. Production exact-plan authority remains closed by default. GUI Start/Stop controls lifecycle only. Stop is serialized with the one-way review/placement boundary: a Stop that wins first prevents a new durable/provider transition; once the effect path wins and durably crosses the accepted boundary, factual completion/classification may finish. A bound pending ENTRY or SELL settles through the accepted RHC3P factual-read path before a new effect is considered. Import, construction and help remain effect-free.

The first RHC4 publication `2f4f50a1df44c261d172f55bc540b635d637cbd9` / tree `558e2f8c1f930d3f15810dea3f01a92ca20fdc24` and mapped run `44181143712` remain preserved; exact-source review rejected that source for `RHC4_STOP_EFFECT_BOUNDARY_RACE` and private-helper coupling. C1 `f3f44e00ec17279ea74445df2b7a680875745f7b` / tree `8dac42fa7039bde8fdb6f6bdd63eeaf432cb049a` and its terminal-red run `44192574584` remain preserved as `PREPUBLICATION_COVERAGE_DEFECT`. C2 corrected route-owned prepublication coverage and stale current seams. Its first clean admission is preserved as `PREPUBLICATION_ADMISSION_PORTABILITY_DEFECT`; the final admission report `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch132-r3n-prepublication-admission\\source-gate-20261118T013037.569843Z\\report.json` recorded FEATURE PASS, PROSPECTIVE_DEVELOP PASS, `IDENTITY_STABLE=True`, `2692 passed, 1 skipped`, Ruff PASS and diff PASS.

Two workflow deviations are preserved without rewriting published history:

- `RHC4_C2_PREPUBLICATION_ATOMICITY_DEVIATION`: one logical C2 correction was published as two previously unpublished commits, substantive `7dfd693b6588f9b3bde24efbe04ba803d08e502b` followed by final portability correction `4f560a74b04ecba85c7b312364a9e4e7b30e57b6`, in one push rather than one terminal atomic candidate. Both commits are now published, exact-reviewed and certified; do not amend or rewrite them.
- `RHC4_C2_TRANSITION_WORKFLOW_REGRESSION`: the first ChatGPT integration command falsely treated the empty stdout of `git diff --quiet` as Boolean state and stopped a clean worktree before integration. The surrounding transition also drifted from the documented procedure by relying on a remembered worktree path instead of rediscovering/re-proving it in the guarded block, omitting untracked-state proof in the first guard, using native fetch/push under `$ErrorActionPreference='Stop'` instead of the reviewed stderr-safe pattern, parsing some native output before first classifying `$LASTEXITCODE`, omitting canonical-origin proof and final develop cleanliness proof, and generating an unnecessarily large PowerShell block. The subsequent read-only diagnostic proved branch/HEAD/tree/upstream/cleanliness exactly before the corrected fast-forward. No source defect, provider effect or partial integration occurred.
- The same transition regression also included process mistakes after integration: a tiny docs closeout was incorrectly delegated instead of handled ChatGPT-direct, automatic continuation was not immediately followed, the already-determined design-only L43-Q1 freeze was initially split from the closeout instead of batched into the same docs-only publication, and stale current Q62 summary rows were not caught on the first closeout review. The existing workflow already contains the correct rules; this closeout follows them rather than changing them.

The first ChatGPT-direct closeout publication `bc5861c53252f870cfb97d7c6f81838d99147347` / tree `e14a6a3a74b0256150abdc5941ad50751a060333` produced docs-only run `44239165344`, attempt 1, terminal FAILURE because the two new L43-Q1 docs contained one extra blank line at EOF. This is `RHC4_C2_CLOSEOUT_C1_DOCS_HYGIENE_DEFECT`: a prepublication hygiene omission in the ChatGPT-direct path, not a source/route/protected-effect failure. The failed run is preserved and is not rerun unchanged.

Q62 is not pending. The accepted tiny-live source was integrated at `f709ec7cc6b610c76e57b9bba7e9484f91897a4f` / tree `369c1e14f201541864c61cb66d718e8efd163940`, and its later protected read-only observation was consumed successfully as `READY_FOR_L43_PROTOTYPE_READ_ONLY / Q62_READ_ONLY_PREREQUISITES_PROVEN`. That result grants no live readiness or trade authority and is `CONSUMED / NO AUTOMATIC RETRY`. RHC2 remains `CONSUMED / PASS / NO RETRY`; RHC3 retained order-scope evidence remains immutable; RHC3P and RHC4-C2 are accepted/integrated. L43 protected effects remain NOT RUN / NOT AUTHORIZED. Q63 remains NOT RUN. `FINAL_HOLDOUT` remains SEALED.

## Current Q1 checkpoint and next boundary

`ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE` is accepted/integrated at `05f4c4700f82c3d40c83f474c3cf614573d48091` / `70aec1c51e63705a68d6710cc3448ac994227e46`. Its first protected read-only observation is consumed as `BLOCKED / QUALIFICATION_INDETERMINATE / NO AUTOMATIC RETRY`; do not rerun it.

The evidence proves the canonical composition and source identity were obtained, but the qualification did not bind an L43 durable-state snapshot. Source inspection shows the production snapshot reader opens only the fixed pre-provisioned `F:\AI\arch147-l43-live-state-v1\durable-state.jsonl` state plus its lock and never initializes it. No production L43 state-provisioning command currently exists; state creation appears only in fake/test fixtures. Because the sanitized Q1 result intentionally suppresses the underlying exception, it does not prove whether the host failure was a missing journal, missing lock, ownership/identity problem or another `L43StateUnavailable` case.

That former standalone state-provisioning successor is superseded as the immediate milestone by Architecture 148. Any L43 state code reused by the new application must be provisioned or migrated as part of 148's complete runtime dependency closure. The consumed Q1 result is preserved and is not rerun. L43/Architecture-148 order effects remain NOT RUN / NOT AUTHORIZED; Q63 remains NOT RUN; `FINAL_HOLDOUT` remains SEALED.

## L41R1, L41R2, and L41R3 historical observations

L41R1 is recorded exactly as
`L41R1_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`. Its preserved evidence is
`F:\\AI\\temp\\arch147-l41r1-schema-observation-f5b81e5f60dc40c280f53007d1db2b52\\evidence.json`,
SHA-256
`2b62f54076fdfd34aa3eb799ed563701f8eadafe8877b25590f88fe72147160f`,
length `1130` bytes. It recorded source admission PASS, one OAuth scope-entry
attempt, one MCP session-open attempt, zero `tools/list` attempts, empty
schemas, reason `L41R1_MCP_SESSION_OPEN_FAILED`, and zero MCP tool, account,
tradability, position, order, portfolio, quote, review, placement, cancellation
and other-tool attempts.

The exact source-contract cause was
`_create_windows_oauth_factory()` installing `_forbid_interactive_oauth`; the
MCP OAuth SDK required an authorization-code flow and invoked that blocker. The
classification is `L41R1_INTERACTIVE_OAUTH_FORBIDDEN`, not a generic browser or
environment failure. The attempt also exposed an upstream OAuth/MCP traceback
output defect: sanitized evidence did not prevent provider/OAuth traceback text
from reaching the terminal.

`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` is a separately named additive successor
with evidence schema `arch147-l41r2-interactive-interface-observation/v1`. It
retains the corrected schema semantics, permits one reviewed interactive OAuth
authorization when persisted state is insufficient, suppresses upstream
provider/OAuth output, invokes only bounded `tools/list`, and records no raw
URLs, callback values, tokens or provider text. Credential reads and writes are
SDK-managed and individually uncounted (`null`/`null`). A successful result is
`CAPTURED_FOR_REVIEW` only; it grants no live readiness, broker authority, Q62
acceptance or order authority. At that historical checkpoint, Q62 was NOT RUN
and blocked pending L41R3 classification.

The L41R2 observation is CONSUMED / BLOCKED / NO RETRY. Its preserved evidence
is
`F:\\AI\\temp\\arch147-l41r2-schema-observation-9a504f5e26b9414998cea287ee13936a\\evidence.json`,
SHA-256
`66C3E5C32A0FD575490B3219AEA7DE2ECCEE65C4E5FDEFF6EB339B9B963FA751`, length
`1386` bytes. It records `L41R2_SCHEMA_MALFORMED`, source HEAD/tree
`d421562703d6bae92b14afdcc1b3defcc595dbc8` /
`b0ca242360b1cfe17222c4b56e95198219eee4be`, and FEATURE plus
PROSPECTIVE_DEVELOP admission PASS. It records one OAuth scope-entry attempt,
one MCP session-open attempt, one browser launch, and one `tools/list` attempt.
MCP tool invocation, account, tradability, positions, orders, portfolio,
quotes, review, placement, cancellation, and other-tool attempt counters are
all zero. Native credential read/write counts are both `null` with accounting
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; automatic retry is FORBIDDEN.

The source extracts `inputSchema`, while MCP SDK v2 Tool objects expose the
Python attribute `input_schema` and retain `inputSchema` on the wire. The
L41R2 fake object fixture used the older camelCase attribute and did not cover
the SDK object model. This is a source/client-model comparison; the consumed
evidence itself does not identify a raw provider object type.

L41R3 is the separately named additive successor with evidence schema
`arch147-l41r3-mcp-v2-interface-observation/v1`. It normalizes only tool name,
description, input schema, and pagination cursor before passing them through
the existing fail-closed sanitized schema parser. It accepts MCP-v2
`input_schema`, wire/mapping `inputSchema`, and the intentionally retained
legacy object attribute `inputSchema`. It preserves one-shot OAuth/session and
browser limits, bounded `tools/list`, zero tool invocations, output
suppression, truthful SDK-managed credential accounting, and no-retry
semantics. `CAPTURED_FOR_REVIEW` grants no Q62 readiness, broker/order or
numeric-rule authority, live eligibility, or `FINAL_HOLDOUT` authority. At the
L41R2 source-acceptance checkpoint, the L41R3 observation had not yet been run;
its later consumed result followed that checkpoint.

The first unpublished L41R2 prepublication admission is preserved at
`F:\\AI\\temp\\arch147-l41r2-source-admission-2804bb15b8ec49eab4f0ac8ac0fe0a0f` and is classified
`PREPUBLICATION_ADMISSION_TOPOLOGY_DEFECT` / `FULL_LANE_DUPLICATE_BASENAME`.
Adding the interactive L41R2 test enlarged the deterministic FULL inventory and
exposed `tests/portfolio/test_models.py` and
`tests/rebalancing/test_models.py` together in broad-5 under the current
top-level pytest import topology. The required invariant observed `40 != 39`
unique basenames. No authority failure occurred, `IDENTITY_STABLE=True`, and
`PROTECTED_EFFECTS=0`; this was not a product-source failure, published red
source, coverage defect, or GitHub CI failure. That first admission remains a
preserved failure. A later fresh admission passed, and the corrected candidate
was published and independently accepted at
`235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`. Mapped FULL run `42358983502`,
attempt 1, was terminal SUCCESS. The real
`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` was later consumed as BLOCKED / NO RETRY;
see the exact evidence record above. At that source-acceptance checkpoint,
L41R3 was its additive successor and had not yet been run against Robinhood;
the later L41R3 observation followed that source-acceptance checkpoint.

## L40 accepted/integrated baseline

L40 is ACCEPTED / INTEGRATED at
`14e1b628c0c51c27b23deabee56eb91859818529` / tree
`48b588cbb37818b0d1edfcbb895cfb715a2bf2d3`. Feature mapped FULL
`41995282653`, attempt 1, was SUCCESS. Develop gate `41997418576`, attempt 1,
was SUCCESS and reused the exact feature certification without duplicate FULL.

The accepted [L40 contract](architecture/147-restricted-live-contract.md)
freezes effect-disabled exact ownership, nonresetting <=$10 requested
new-acquisition budget, truthful reducing-exit notional/fill semantics,
partial-fill ownership, residual preservation, identity binding and
UNKNOWN/no-retry behavior. It grants no provider/order authority and does not
authenticate caller-supplied evidence references.

At L40 closeout, the remaining path started with the L41 read-only Robinhood
fractional-exit capability observer, followed by durable ownership/budget,
runtime signal, application, readiness/recovery, and live qualification work.
That L40 plan is historical; the current source-preparation state and next step
are recorded above. `FINAL_HOLDOUT` remains sealed.

Accepted/integrated D34 source:
`b86defebf9ccbf1efb91397de8f2e66db24a6665` / tree
`9fa2360dfe7afdd902fd539e94f888063439785d`. Feature mapped FULL
`41969407894`, attempt 1, and develop source-gate `41973853073`, attempt 1,
succeeded; develop reused the exact feature certification. D34's accepted
source descends from the integrated D33 source
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9` through the preserved first D34
publication `9981bf47072d35381a2e5b6f187c9497e9dbed5a`.

D30 is ACCEPTED with dataset semantic ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA-256
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
price basis `ALPACA_ALL_ADJUSTED_PRICE_V1`.

D31's exact research bundle is ACCEPTED: campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA-256
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, and
selection `NONE_QUALIFIES`. The retained control is `BASE_MA35_50_V1` with
candidate ID `21158358-75be-5597-b940-5bccdda1429c`. NONE_QUALIFIES means that
neither challenger qualified; it is not a winning challenger, promotion,
profitability proof, or live eligibility.

D32 is ACCEPTED / CLOSED: strategy math parity, research-binding integrity, and
live data-basis parity all passed; the 2,516 strategy comparisons had zero
mismatches, and the accepted D34 observation used the same
`ALPACA_ALL_ADJUSTED_PRICE_V1` basis as D30/D31. The former
`DATA_BASIS_MISMATCH` blocker is closed. Alpaca all-adjusted SIP/USD signal data
and Robinhood broker/account/execution/custody remain separate providers with
no fallback.

D33's real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Preserved
evidence: `F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`,
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes; observation `2026-11-04T23:59:08.218729Z`; credentials `1`;
provider requests `1`; selected sessions `60`; all prohibited-effect counters
are zero. D33 discarded the safe failure subtype, so the exact provider
rejection subtype is unavailable. Its request end exceeded observation through
end-of-calendar-day semantics; that is a source defect, not a proven provider
rejection cause.

The first D34 publication is preserved at
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`; mapped run `41950572892`, attempt
1, was terminal SUCCESS, but exact-source review rejected it before develop
integration. The review found incomplete blocked-result attempt-count
invariants and an operator-level escaped-failure fallback that could fabricate
zero credential/provider counts. No D34 real provider observation occurred.

D34 is now ACCEPTED, INTEGRATED, and CONSUMED SUCCESSFULLY. The accepted
read-only observation is recorded at
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`,
observation timestamp `2026-11-05T05:28:41.664723Z`. It consumed exactly one
credential read and one provider call, with no retry. The one SPY daily request
ended at the exact published XNYS regular close
`2026-11-04T21:00:00.000000Z`; response-body SHA-256 is
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94`, and the
`CompletedSignalInputs` digest is
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.
Production, broker, runtime-binding, campaign, paper, live, and
`FINAL_HOLDOUT` counters remained zero. The observation validates the signal
input basis only; it does not authorize an order or grant live eligibility.

## Product and protected boundaries

The product remains a private single-user Windows desktop application with
explicit Start/Stop and manual stopped-state updates. Credentials and durable
state remain outside disposable source files. Live trading is disabled; no real
order is authorized. Readiness labels are not granted by source publication,
source admission, or provider-data parity alone.

Historical P6, P5A/P5B, and earlier architecture evidence remains available in
its owning documents. The current handoff and Architecture 147 validation
ledger record the bounded continuation identity and acceptance state.
