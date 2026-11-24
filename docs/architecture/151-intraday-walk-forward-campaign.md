# Architecture 151 — Intraday walk-forward campaign

**Status:** the frozen design and source-foundation contracts are documented here. This document does not assert exact-source acceptance, integration, or a mapped CI outcome. No real strategy replay or data-custody access has occurred. Architecture 150 remains immutable negative evidence.

## 1. Purpose and information boundary

Architecture 151 defines a synthetic-testable source foundation for a bounded, long-or-flat intraday research campaign. It owns the immutable strategy population, canonical identities, sparse causal feature contracts, walk-forward chronology, economic and qualification contracts, trial accounting, ranking rules, and fail-closed information boundaries. The foundation is not a market-data reader or a strategy replay engine.

Only calendar-published XNYS sessions in 2016–2023 are visible to development. Calibration uses only eligible complete history strictly before each scored year. The 2024–2025 period remains sealed until a single Arch151 candidate is frozen, and Jan–Oct 2026 remains sealed until that same candidate passes the authorized holdout. A zero-candidate freeze terminates the campaign without opening 2024+. No source foundation API reads those periods.

No accepted-custody files, credentials, providers, Robinhood, brokers, paper/live effects, or production mutation are authorized by this architecture. Architecture 150 implementation, tests, artifacts, and evidence are immutable. Its failed G1 results are negative evidence and are not re-run or used to mutate its population.

## 2. Canonical program grammar and identity

The grammar is closed to exactly four frozen families and sixteen structural programs. Each family contains exactly two 5-minute and two 15-minute programs. Each program has exactly two ordered execution-symbol slots, SPY then QQQ, for 32 immutable slots total. There is no caller-selected subset, mutable parameter map, result-dependent generator, or alternate population.

The identity schemas are `arch151-intraday-walkforward-program/v1`, `arch151-intraday-walkforward-trial-slot/v1`, and `arch151-intraday-walkforward-population/v1`. All identities bind semantic version `arch151-frozen-design-2026-11-23/v1`. The root UUID namespace is UUID5 of `NAMESPACE_URL` and seed `urn:ai-trading-bot:arch151:intraday-walkforward-foundation:v1`; child namespaces are UUID5 of that root and versioned labels (`program-identity/v1`, `trial-slot-identity/v1`, and `population-identity/v1`). Canonical material uses sorted-key compact UTF-8 JSON. Decimal identity text is finite fixed-point text with trailing fractional zeroes removed and zero rendered as `0`; it is independent of locale and ambient Decimal context.

A program UUID and SHA-256 fingerprint bind its schema, semantic version, key, family, resolution, ET entry window, and every parameter below. A slot identity binds the complete canonical program identity and its execution symbol. The manifest UUID and fingerprint bind the complete ordered sixteen-program and thirty-two-slot population. Source import rejects changes to canonical order or population shape.

The canonical manifest is `4fdce706-4322-59e1-95d1-590a39e67978`, fingerprint `8a5c89c55388e8ec5d0c6384a8f69ab99587a538bd0d868cb29a108717084083`.

### Family A — Regime-filtered noise/VWAP breakout

| Program | Program UUID | Fingerprint | Resolution; entry window (ET) | Complete frozen parameters |
|---|---|---|---|---|
| A5-01 | `1427b23a-aa27-55a2-a1a4-2a6d3895fe8e` | `496d29fe3d4056768ab6676f178b30e00291d9419f71d702af73147e7841cb4c` | 5m; 10:00–14:30 | noise lookback 20 sessions; breakout multiplier 0.75; confirmation 2 bars; regime lookback 60 sessions; regime multiplier 1.25; stop multiplier 1.25; trail activation 1R; trail distance 1R; max hold 60 minutes; one entry/session |
| A5-02 | `22d2da5e-3a0f-518f-b4fa-672926ecf8a7` | `2535c516422af3174431861b003e4c67da152501d24a4a6fb63a3b7a7ecb7df9` | 5m; 10:30–13:30 | noise lookback 40; breakout multiplier 1.00; confirmation 3 bars; regime lookback 60; regime multiplier 1.10; stop multiplier 1.50; trail activation 1.5R; trail distance 1R; max hold 90 minutes; one entry/session |
| A15-01 | `1dea3258-f9ff-5ac1-b682-233f26b8bbf7` | `22810e8fdd070f62638aa572018c726e337b95f8d76adc1dfbe6ee54289fa408` | 15m; 10:00–14:00 | noise lookback 20; breakout multiplier 0.75; confirmation 2 bars; regime lookback 60; regime multiplier 1.25; stop multiplier 1.25; trail activation 1.5R; trail distance 1R; max hold 120 minutes; one entry/session |
| A15-02 | `399778ed-fc7e-5f3e-a873-f4b9bb33f623` | `4a1a30d1b8fd340746ea6c1c81def6c8889433796e8856495a94282c01135a7b` | 15m; 10:30–13:00 | noise lookback 40; breakout multiplier 1.00; confirmation 2 bars; regime lookback 60; regime multiplier 1.10; stop multiplier 1.50; trail activation 2R; trail distance 1.25R; max hold 180 minutes; one entry/session |

### Family B — Opening-range breakout retest

| Program | Program UUID | Fingerprint | Resolution; entry window (ET) | Complete frozen parameters |
|---|---|---|---|---|
| B5-01 | `90332549-bd19-5829-b6b7-24e04aad9762` | `099d5a316e8329590d49c731aafced726aa909c4d2e3c4c401c0780c3901eb1b` | 5m; 10:00–12:00 | opening range 30 minutes; breakout buffer 5bp; breakout confirmation 1 bar; retest deadline 6 subsequent bars; retest tolerance 10bp; reclaim confirmation 1 close; stop buffer 5bp; target 2R; no trailing stop; max hold 90 minutes; one entry/session |
| B5-02 | `690af06e-7f77-5a65-b15e-ead9b3c0f747` | `c91755a7593d0c0425a21baad773172754b1f360946ddf65c0d06fa506fdde51` | 5m; 10:15–13:00 | opening range 45 minutes; breakout buffer 10bp; breakout confirmation 2 bars; retest deadline 8 subsequent bars; retest tolerance 5bp; reclaim confirmation 2 consecutive closes; stop buffer 5bp; target 1.5R; trail activation 1R using prior completed bar low; max hold 120 minutes; one entry/session |
| B15-01 | `e3c57e33-3392-5587-b1ed-4793f087df4b` | `e2e20b98a8ed364977e69ab4766a5f8b1c57ec935315ff9fb84b46a8ba48a177` | 15m; 10:00–12:00 | opening range 30 minutes; breakout buffer 5bp; breakout confirmation 1 bar; retest deadline 4 subsequent bars; retest tolerance 10bp; reclaim confirmation 1 close; stop buffer 5bp; target 2R; no trailing stop; max hold 120 minutes; one entry/session |
| B15-02 | `c2d37aa5-d5e6-523e-8d70-2d36b41fc7c7` | `06cdd0ae08b5c7a1777e00aebadaeaecd2b9f1aa3ad39dfce4f5045dfd380543` | 15m; 10:30–13:00 | opening range 60 minutes; breakout buffer 10bp; breakout confirmation 2 bars; retest deadline 3 subsequent bars; retest tolerance 5bp; reclaim confirmation 2 consecutive closes; stop buffer 5bp; target 1.5R; trail activation 1R using prior completed bar low; max hold 180 minutes; one entry/session |

### Family C — VWAP-deviation mean reversion

| Program | Program UUID | Fingerprint | Resolution; entry window (ET) | Complete frozen parameters |
|---|---|---|---|---|
| C5-01 | `1c8ae358-15bf-577a-a574-32332aad50ed` | `c53e35e49d1fd83a77a42913f9dffb2616dc39390f75c39546af6110d5ebe095` | 5m; 10:00–14:00 | deviation sample lookback 12 bars; entry 2.00σ; efficiency-ratio lookback 24; maximum ER 0.30; exit offset 0σ (current VWAP); stop 1.5σ; max hold 60 minutes; cooldown 30 minutes; maximum 2 entries/session |
| C5-02 | `34e3249f-7388-5b51-b081-5cadb39b7d72` | `9111c87ef5ce420d6fec65d2f6b1df921dfcb57ab747502940144c436b50db97` | 5m; 10:30–13:00 | deviation lookback 24; entry 2.50σ; ER lookback **30**; maximum ER 0.25; exit offset 0.25σ; stop 2.0σ; max hold 90 minutes; cooldown 45 minutes; maximum 2 entries/session |
| C15-01 | `67b50527-cbce-5406-8e16-de7c1753723e` | `4af085b17e72c5fb1f907b76431cb84df520adb7adc22c574ae1778e09adc18c` | 15m; 10:30–14:00 | deviation lookback 8; entry 1.75σ; ER lookback 12; maximum ER 0.30; exit offset 0σ (current VWAP); stop 1.5σ; max hold 120 minutes; cooldown 45 minutes; maximum 2 entries/session |
| C15-02 | `8a6d9a19-eefc-5a80-a7aa-375b8ecb5925` | `885818681c2cc74dc2ce9c018c84f3ca48ab8a78be85f4a40209bab287d1e21e` | 15m; 11:00–**14:00** | deviation lookback 12; entry 2.25σ; ER lookback **10**; maximum ER 0.25; exit offset 0.25σ; stop 2.0σ; max hold 180 minutes; cooldown 60 minutes; maximum 2 entries/session |

### Family D — Cross-ETF confirmed trend pullback

| Program | Program UUID | Fingerprint | Resolution; entry window (ET) | Complete frozen parameters |
|---|---|---|---|---|
| D5-01 | `48e9556e-aa92-5f85-b20f-3e9112f99ba3` | `492c9d87daecbbecd80f3906f1b8a35a3acc74303aafebe915ad3023f00d5474` | 5m; 11:30–14:00 | fast/slow EMA 8/21; rising confirmation 2 bars; ATR lookback 14; swing-peak window 6 bars; pullback depth 0.25–0.75 ATR; reclaim 1 close within 3 bars; stop buffer 0.25 ATR; trail activation 1.5R; trail distance 1 ATR; max hold 90 minutes; one entry/session |
| D5-02 | `4212a93e-0636-5892-9c06-ff3ce43eb96b` | `ac382ef548c6a26c7b7bfaf47adaffc56cbd6cba1f1897b5f5beec169943c380` | 5m; 12:15–14:00 | EMA 12/26; rising confirmation 2 bars; ATR lookback 14; swing window 8 bars; pullback 0.50–1.00 ATR; reclaim 2 closes within 4 bars; stop buffer 0.50 ATR; trail activation 2R; trail distance 1.5 ATR; max hold 120 minutes; one entry/session |
| D15-01 | `1148eee4-81b6-5a23-9c1b-5601b8beac3a` | `09ccce6f56479ab10c461f2d8418d712a9b55e1a4577c2aa4aa44d65e6202e66` | 15m; 11:30–14:00 | EMA 3/8; rising confirmation 2 bars; ATR lookback **8**; swing window 4 bars; pullback 0.25–0.75 ATR; reclaim 1 close within 2 bars; stop buffer 0.25 ATR; trail activation 1.5R; trail distance 1 ATR; max hold 180 minutes; one entry/session |
| D15-02 | `46dc53a4-2b3a-5a4f-bae9-02b6dd38c693` | `2e169fd74d7ba3b22b2e4378a36e343adb31b8b8fc917408dca9f616fa11a3ce` | 15m; 12:00–14:00 | EMA 4/10; rising confirmation 2 bars; ATR lookback **10**; swing window 6 bars; pullback 0.50–1.00 ATR; reclaim 2 closes within 3 bars; stop buffer 0.50 ATR; trail activation 2R; trail distance 1.5 ATR; max hold 240 minutes; one entry/session |

### Ordered slots

Every program expands to SPY followed by QQQ. The following table is the complete ordered slot population; no slot may be added, removed, or reordered.

| Program order | SPY slot UUID | QQQ slot UUID |
|---|---|---|
| A5-01 | `c936e231-e43b-543e-bfbe-3a6e1725eb41` | `1a792ac0-6f9e-5238-b3e8-5aa891bd4abb` |
| A5-02 | `4203cf1a-7eed-50bd-9a0a-745ee7c895b9` | `a214ad6d-6b65-5028-b396-71cc54835e85` |
| A15-01 | `2a95416b-346b-567f-8e03-eb7ddb02a434` | `e19015b2-a974-593d-85b0-bfe6588cd490` |
| A15-02 | `43494976-a0e9-5a96-a316-21f5998c5afd` | `a3b2f65f-e7d7-5099-8679-a0a417fd8521` |
| B5-01 | `369a2054-940c-5897-8f6a-c4a1fcfa3147` | `171c6863-102c-5bc0-8002-581b5bd95076` |
| B5-02 | `a0228f41-53c9-5179-af2d-17e286a0933b` | `009dced6-ad82-5ddc-a64d-bf1e6c910b93` |
| B15-01 | `2206cefb-5177-5b76-9595-41327fdcec5c` | `daf4e3a5-8378-58d4-b7a0-a3d51fb6e818` |
| B15-02 | `613a3d19-d953-57ae-8fed-9e416bb7b062` | `5ca09231-49f7-5f6d-b7ac-b008258e406e` |
| C5-01 | `b7778e31-0d3c-54ea-a03f-e118cb0e2c4d` | `83bc96c9-db55-5cfa-826f-4b4e66a2ed2b` |
| C5-02 | `fd667c21-815e-5c29-9197-63cf8b6d9e70` | `bd4190c2-2faa-50a8-9d2d-dd8d9b74521b` |
| C15-01 | `d4c6a80b-4cca-5125-af5d-6aa09e8f77e6` | `40696e44-52b6-5cd4-ace4-09464b13d0ab` |
| C15-02 | `7c30ae58-9efb-5c8b-8198-231dd9ee6258` | `094c5d78-5195-5e4d-9a49-cc361df4333d` |
| D5-01 | `d3a4a2b9-8025-5e4f-a24e-4a9c69060bad` | `ab05cae8-6ca1-5c93-acd0-3544fce73fb1` |
| D5-02 | `83b545c3-1c4a-5c4a-be0e-edf8d1d99c94` | `ddf859c6-b498-534f-a16f-fa91399e8859` |
| D15-01 | `8e1357b9-5a0c-5142-b2f2-65dcc6e1c32e` | `f340cec1-e5f9-5ea7-a8bb-c1d960ad828c` |
| D15-02 | `7ca2fae2-7003-573a-b41b-c26a223f5ab6` | `a84e8d52-44e4-5107-b155-0843a54f49a4` |

## 3. Sparse data and shared causal features

Aggregation is anchored to each published XNYS regular-session open, including the published early-close schedule. A 5-minute bar exists only when all five exact scheduled one-minute constituents are present; a 15-minute bar exists only when all fifteen are present. Constituents must share the session, align to the published grid, and finish no later than the scheduled close. A missing constituent removes that aggregate decision point. No aggregate crosses a session boundary or early close, and no OHLCV is synthesized. Stateful confirmation and setup logic resets at a missing aggregate bucket and cannot bridge it.

Session VWAP is derived only from observed eligible one-minute HLC3 multiplied by actual observed volume, cumulatively within the session. It resets at each session, requires the source stream to begin at the published open, rejects invalid or zero denominators, and does not fill, carry, interpolate, or borrow values. Aggregate VWAP observations must bind to the exact complete aggregate bars and aligned timestamps.

### Family A — historical noise and regime calibration

Every Family A measure is an immutable SPY- or QQQ-tagged record with an explicit scope and a SHA-256 source digest. The digest binds the canonical exact one-minute observations used to derive it. A historical measure requires every scheduled one-minute observation for the published session through its close, including early closes, and stores the first-30-minute return from that complete source session. A current scored-session measure requires exactly the 30 scheduled opening minutes and no later observations, so it is available causally without waiting for the rest of the session. Calibration rejects mixed-symbol history; the calibration record and its canonical UUID/fingerprint bind the instrument, program, scored year, calibrated values, and each selected historical measure's source digest. The current opening measure and every confirmation bar must use the calibration's same symbol.

For each complete historical session, first-30-minute absolute return is the dimensionless value `abs(first_30m_close / session_open - 1)`. N20 and N40 are medians of that value over the required 20 or 40 prior complete eligible sessions. The regime statistic is the median over 60 prior complete eligible sessions. “Complete” is determined from the published session calendar and the exact scheduled observations; the current session must also have its complete first-30-minute window before its signal can qualify.

Each fold derives its historical noise and regime thresholds from the last required eligible sessions strictly before the scored year begins. Those calibrated values are frozen for the entire scored year; scored-year observations may not update calibration. Breakout threshold is `session_open * (1 + breakout_multiplier * N)`. Initial stop distance is `entry_reference_price * stop_multiplier * N`, not a dollar distance equal to `stop_multiplier * N`. Initial R is the strictly positive pre-cost distance from entry reference to stop; invalid/nonpositive risk is rejected. Confirmation uses contiguous completed aggregate bars and strictly rising contemporaneous VWAP across the confirmation sequence. The program's entry window applies to the final qualifying confirmation bar; earlier contiguous confirmation bars may precede it.

### Family B — opening-range retest state

Opening-range observations must be complete, session-aligned, and anchored at the published session open. The breakout level is `opening_range_high * (1 + breakout_buffer_bps / 10000)`; retest tolerance is a relative price band around that frozen level. Breakout confirmation, retest, and reclaim must occur on chronologically distinct completed bars. Retest deadline starts after the final breakout-confirmation bar and counts subsequent complete bars only. Reclaim begins after the retest and requires the declared consecutive completed closes above the level. A failed breakout/retest/reclaim sequence or missing post-open aggregate bucket invalidates all state for that setup. A later eligible complete bar may begin a fresh independent breakout sequence; no confirmation, retest, reclaim, or deadline state carries across the invalidation. The public predicate emits only when the final supplied completed bar establishes the reclaim, and the signal timestamp is that bar's completion timestamp. An incomplete or missing opening-range constituent still fails the entire session input closed.

The stop is based on the lowest low observed from retest through reclaim, reduced by the specified relative 5bp buffer. Target is measured from the initial positive R. Any trailing stop is monotonic and takes effect prospectively after the bar that established it. This family is limited to one entry per session.

### Family C — VWAP deviation and efficiency ratio

Normalized deviation is `d_t = close_t / VWAP_t - 1`. Sigma is the sample standard deviation of the specified prior contiguous completed-bar deviations, excluding the signal bar. Entry requires `d_t <= -entry_sigma_multiplier * sigma`. Stop distance is `entry_reference_price * stop_sigma_multiplier * sigma`. Entry sigma is frozen for the initial stop and sigma-based reversion target. A positive exit-sigma offset uses current causal VWAP multiplied by `(1 + exit_sigma_multiplier * entry_sigma)`; a zero offset exits against current causal VWAP.

Efficiency ratio over L periods requires L+1 contiguous completed closes and is `abs(close_t - close_(t-L)) / sum(abs(adjacent_close_changes))`. Insufficient warmup, unavailable, undefined, nonfinite, or zero-denominator indicators are rejected. Session-local indicators reset at each new session and never bridge missing buckets. Cooldown uses elapsed session/wall-clock time. The corrected C5-02 ER lookback is 30 and C15-02 ER lookback is 10; C15-02's entry window ends at 14:00 ET.

### Family D — cross-ETF confirmed trend pullback

EMA state is maintained independently for each symbol within the session, seeded by the simple average of the initial required contiguous complete closes, then updated with `alpha = 2 / (n + 1)`. The slow EMA must be initialized and the declared rising confirmation observed. Each symbol's EMA and contiguous state reset after its own missing aggregate bucket and must complete a fresh SMA warmup. Family D setup/confirmation evaluation uses only the exact timestamp overlap of both symbol streams, divided into contiguous aligned segments; a gap in either stream resets the paired setup and cross-confirmation state. ATR is the arithmetic mean of the preceding required contiguous true ranges, excluding the current decision bar; a genuine preceding close is required for true range. After a gap, swing, pullback, ATR, and reclaim warmup must be available within the new aligned segment before a signal can form. The corresponding other-ETF confirmation uses identical EMA horizons, and both confirmation bars must have exactly aligned timestamps. Stale cross-ETF observations are not substituted. Insufficient remaining session time to rebuild the required state produces no signal.

The reference swing peak is the maximum high in the declared preceding contiguous peak window, excluding the first pullback bar. Pullback depth is measured from that frozen peak to the lowest subsequent completed pullback low, normalized by ATR frozen when setup is established. The first pullback must reach the minimum and not exceed the maximum; subsequent excessive depth or any missing required bucket invalidates the setup. Reclaim begins after pullback establishment and requires the declared consecutive completed closes above both the prior completed bar high and contemporaneous fast EMA, within its deadline. Final reclaim eligibility requires both the local trend gate and exact-time cross-ETF confirmation.

Setup ATR is frozen for the initial stop buffer, R, and trailing distance. R must be positive. Trailing changes are monotonic and prospective. Corrected D15-01 and D15-02 ATR lookbacks are 8 and 10.

## 4. Typed shared execution policy (not a replay engine)

The foundation exposes closed, immutable policy fields and enums only. It does not implement a position loop, fill engine, or actual strategy replay.

- Decisions use completed bars with unambiguous bar and completion timestamps. Signals are eligible only within their frozen New York session-relative entry window.
- A signal may enter only at the immediately following scheduled eligible one-minute open, if that minute is observed and remains inside the entry window. An absent entry minute expires the signal; the implementation cannot chase a later observed price.
- Each slot is evaluated independently as unleveraged long-or-flat. Averaging down, pyramiding, overnight positions, and combined multi-slot allocation are forbidden. Global maximum is two completed round trips per session; Family B allows at most one entry per session.
- BASE cost is 2 basis points per fill, STRESS is 5 basis points per fill, and ZERO is diagnostic only. Apply adverse costs once per actual fill. A target uses its gross target reference before costs.
- A stop gap through the stop uses the observed opening reference; otherwise an observed stop touch uses the stop reference. If stop and target are both touched in an ambiguous observed minute, resolve in favor of the stop. Trailing updates from a completed bar become effective only on subsequent observations and remain monotonic.
- Completed-bar reversion exits execute at the next observed eligible one-minute open. Maximum hold and cooldown use elapsed wall-clock/session time, including absent minutes. A pending mandatory exit remains pending across a missing observation.
- Mandatory liquidation begins five minutes before the published session close. Exit at the first observed eligible one-minute open at or after the liquidation time and before the close. No new entry is allowed at or after the liquidation boundary, including early-close sessions. If required observations are absent and liquidation cannot occur, fail the replay closed and preserve complete failure evidence; never delete the trade or manufacture a fill.
- Never designate the final observed bar retrospectively as if its status were known at the decision time. Frequency denominators remain the full published XNYS session population.
- VWAP uses only observed eligible one-minute HLC3 and actual volume. Missing data is never filled, interpolated, carried forward, synthesized, or borrowed from the other ETF.

These are source-owned execution semantics. Position accounting, actual fills, mandatory exit tracking, evidence preservation through a complete replay, and production replay authority remain evaluator-owned work.

## 5. Walk-forward folds and evaluation records

The five immutable expanding folds are:

| Fold | Calibration interval | Scored interval |
|---|---|---|
| WF1 | 2016-01-01 through 2018-12-31 | 2019 |
| WF2 | 2016-01-01 through 2019-12-31 | 2020 |
| WF3 | 2016-01-01 through 2020-12-31 | 2021 |
| WF4 | 2016-01-01 through 2021-12-31 | 2022 |
| WF5 | 2016-01-01 through 2022-12-31 | 2023 |

Fold identity binds its exact calibration start/end, scored start/end, and year. A development batch contains exactly five fold records for one canonical slot, each recorded under each of BASE, STRESS, and ZERO: 15 immutable records per slot. The batch rejects missing/duplicate folds, changed program or slot identity, wrong symbol, invalid chronology, mixed economics, or altered fold identity. ZERO records are diagnostic and cannot replace STRESS qualification. Scored-year observations may update explicitly causal intraday state, but never frozen calibration or structural parameters.

## 6. Metrics and development qualification

Metrics derive from complete published XNYS session vectors. Annual net return compounds the chronological full-session daily returns. STRESS aggregate net return compounds the chronological 2019–2023 session path. Profit factor is total gross positive completed-trade net P&L divided by total absolute gross negative completed-trade net P&L; an absent or zero loss denominator is undefined and rejected. Maximum drawdown is calculated from the concatenated chronological full-session equity path across all five years, retaining cross-year drawdowns. Positive-year counts and yearly profit factors use the five exact scored folds. Frequency uses the full published session population, not only sessions with observed bars or trades.

Development qualification uses STRESS and has exactly these nine independent requirements:

1. Aggregate 2019–2023 net return is greater than 0.
2. Aggregate profit factor is greater than 1.
3. Net return is positive in at least four of five scored years.
4. Profit factor is greater than 1 in at least four of five scored years.
5. Worst scored-year return is greater than -10%.
6. Maximum drawdown is at most 20%.
7. Average completed round trips per year is at least 100.
8. Active-session fraction is at least 35%.
9. Median completed round trips per active session is at most 2.

An undefined, unavailable, nonfinite, or inconsistent metric cannot qualify. Sharpe is descriptive/ranking-only and is not an additional development threshold. Turnover is supplied by the evaluator as one finite nonnegative annual value per scored fold; the foundation does not infer it from trade frequency. Ranking turnover is the arithmetic mean of the five annual values. The current architecture does not define the underlying turnover calculation, which remains evaluator-owned.

## 7. Prior-trial accounting and selection-bias contract

The source-owned prior-intraday ledger binds these distinct hypotheses and immutable evidence references:

| Campaign | Distinct keys counted | Count | Report UUID | Report SHA-256 | Source commit | Manifest / slot evidence |
|---|---|---:|---|---|---|---|
| Arch148 churn | `CONTROL`; `OPPOSITE_CONFIRMATION_EXIT`; `OPPOSITE_EXIT_COOLDOWN_15M`; `OPPOSITE_EXIT_COOLDOWN_30M` | 4 | `19dcca18-7080-541d-9864-d730c68471e0` | `5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8` | `be30617594e197f372438dba19d325fd8737b850` | CONTROL counted once; repeated baseline observations deduplicated |
| Arch148 late opening drive | `OPENING_DRIVE_LATE_CAPTURE_V1` | 1 | `42355698-d57e-5f6b-8347-6a752e5b4572` | `e6349ea0c7f1e1b09f165bede8c93b68fb6bc6168940fda0ae2270bf9079f19b` | `370ebccf52a61e91979bc61efaac0001dd563be6` | One distinct hypothesis |
| Arch150 G1 | 24 exact program-symbol slots | 24 | `22f752aa-5dc1-5e42-af29-1c7e2f921175` | `d3b637f410b9e8bf05d352e50efea95721151543ec6308fc270c804b5aa372c7` | `4df84db43833edc0d1b644e2116acdfdccc5897b` | Manifest `7e179cbc-18cf-59ce-9116-899cc876ece0`; exact slot UUIDs below |

Ledger scope follows distinct hypotheses, not acquisition or requalification attempts: the [B1 contract](../validation/arch148-b1-intraday-contract.md) defines the frozen data/backtest contract, while B2 attempts `fd8aa...` and `bb1a...` are distinct acquisition attempts rather than distinct strategy hypotheses ([B2 acquisition plan](../validation/arch148-b2-readonly-acquisition-plan.md)). The accepted sparse offline requalification and baseline are reused as the Arch148 churn `CONTROL` and counted once; its three other named variants count separately ([churn report](../validation/arch148-churn-research.md)). The late-opening-drive report defines one fixed `OPENING_DRIVE_LATE_CAPTURE_V1` candidate ([late-opening-drive research](../validation/arch148-intraday-momentum-research.md)).

The 24 Arch150 G1 slot keys, in canonical ledger order, are:

```text
69e38e92-3748-53e4-a24f-a700c04386c3
05b34c9f-4aa3-5b32-99ee-e76de7d30682
612e820a-25c6-56eb-ac95-fbf943352842
e771607a-3c78-5bb9-970a-7e0bb34da4bd
fae4d0b5-348d-5ba4-a7ea-e2d75512a09d
3e4b5053-b17e-582b-851e-c8c9927e524a
4fdc7fe8-6845-5e1c-8aa8-a3d679f77aa3
03532ff1-5c9a-5772-8d07-f905560c7800
ad36a3fb-90ce-552a-81a6-a8791bba47d0
5646b3cb-0bfb-54cf-8131-d3237cabfcd2
59db62c4-3d17-5e73-9f94-20e516b25b5a
11e66a27-c0a7-516e-b810-37ef5c4bcb78
db72c3a0-3291-5eec-b6d3-0d8546b8cd75
a5a4d9cb-c97f-5e71-b2b5-44137eb6e637
30b0716b-4949-5bd6-8ab8-c582c8e5d3d6
997cc95c-5e7c-5252-85bf-3a76d705ca4e
5d19627f-25ec-5e76-961e-3d6ac86224df
7aa841e8-0e9f-5eef-89e1-4f3f377a1fc6
f55fc548-6597-5d23-a7f6-1152879f76d9
63c665ab-8fc7-5feb-9b20-cdb25f702685
1190874c-23af-503f-8b2f-4be6c8a1da85
3d79db4f-f1a0-56da-a5fd-4438c6689fdc
b80e9148-1620-5f47-9a8e-a2dc89468efd
c0ea9f0b-8dc4-573b-932e-4777d1817dcb
```

The inclusive documented count is `4 + 1 + 24 = 29`. Repeated observations, cost scenarios, and reporting slices are not additional hypotheses. Arch147/daily work and Arch148 B1/B2 acquisition are excluded because they are not additional distinct intraday search trials. The canonical campaign audit found no further unique current intraday trials. Effective trial count is mechanically `max(64, 32 + documented_prior_intraday_trials) = max(64, 32 + 29) = 64`.

The source-owned selection-bias input binds the full canonical population, prior-trial ledger identity/fingerprint, effective trial count, and provenance. Eventual DSR or reviewed-equivalent probability must be at least 0.95. There is no assumed Sharpe benchmark and no externally supplied unverified float may qualify a candidate. The statistical calculation and independent review are deferred to the evaluator milestone; the current production producer is unavailable and fails closed.

Descriptive ranking preserves the full 32-slot population and uses this lexicographic order: DSR probability descending; worst scored-year return descending; STRESS profit factor descending; STRESS Sharpe descending; maximum drawdown ascending; mean five-year turnover ascending; immutable slot UUID ascending. Undefined Sharpe is unavailable for ranking. Synthetic ranking records exercise ordering only; they are untrusted and cannot authorize qualification, final freeze, or data access.

## 8. Zero-or-one freeze and holdout firewall

The final-freeze policy accepts only the complete source-owned 32-slot development population and exact five-fold/three-economics evidence. It may freeze zero or one candidate, never more. Because no reviewed DSR producer exists in this foundation, the production freeze currently returns zero candidates. Caller-supplied UUIDs, result records, success Booleans, synthetic ranking material, or a selected subset cannot create a candidate or unlock a boundary.

Holdout authorization must bind the exact source-owned freeze and complete authenticated development evidence. Extension authorization must bind the same frozen candidate plus a valid authenticated holdout PASS. The source foundation has no reader, opener, or acquisition path for 2024–2025 or Jan–Oct 2026; both remain sealed under their stated gates.

## 9. Implementation ownership and deferred evaluator work

The current source foundation owns typed grammar and manifest identity, sparse aggregation and session VWAP, pure causal family signal/setup primitives, the shared immutable execution-policy contract, fold/economic/qualification records, the exact prior-trial ledger, descriptive ranking, zero-or-one freeze policy, and fail-closed holdout/extension authorization types.

The following remain evaluator-owned and must be independently designed, reviewed, tested, and authorized before any actual data use: actual DSR/equivalent statistical computation and provenance; authenticated development/holdout result issuance; custody access and real strategy replay; position and fill accounting; stop/target execution, recovery, mandatory liquidation and full failure evidence; and 2024/2026 authorization/opening checks. No complete replay engine is claimed here.
