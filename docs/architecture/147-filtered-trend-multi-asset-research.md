# Architecture 147 — Filtered-trend multi-asset research

Status: source, ADX C1 and C2 accepted/integrated; real adjusted acquisition
and the frozen campaign complete. B1 binding and corrected B2 OPEN_REPLAY
smoke are complete; current next boundary is separately owned
[P5B-lite read/account/reconciliation](147-p5b-robinhood-read-reconciliation.md).
Checkpoint: `arch147-filtered-trend-multi-asset-research`.
Branch: `feature/research-filtered-trend-multi-asset-current`.
Canonical certification: GitHub-owned FULL; preflight=None; execute=None.

## Frozen data contract

This is an independent dataset profile. Accepted P2/P3 SPY RAW / PRICE_RETURN
source, artifacts, identities and FINAL_HOLDOUT are unchanged. Fixed ordered
universe: SPY (US large-cap), QQQ (Nasdaq/growth), IWM (small cap), EFA
(developed international), EEM (emerging markets), TLT (long-duration Treasuries),
GLD (gold), PDBC (commodities). IEF/VNQ and individual stocks are deferred.
No universe expansion after results are observed.

`ALPACA_ALL_ADJUSTED_PRICE_V1` means Alpaca daily SIP/USD bars with
`adjustment=all`: split-adjusted prices/volume, cash-dividend price adjustment,
and spin-off price adjustment. The [official historical bars contract](https://docs.alpaca.markets/us/reference/stockbars)
defines these adjustments but supplies no exact dividend-reinvestment formula.
This profile therefore does not relabel the data `AdjustmentType.TOTAL_RETURN`
or claim an exact investable dividend-reinvestment total return. Returns are
returns on that adjusted price series, with simulated whole adjusted-share units.
Cash distributions are represented through provider price adjustment, never
credited a second time. Provider revisions or adjustment vintages create new
dataset identities; these are not point-in-time vintage claims.

The existing typed `TOTAL_RETURN` means total-return data in generic market-data
contracts and is not proof of this provider behavior. Existing backtest/research
adapters explicitly require RAW in relevant historical contracts. Reuse of those
adapters would mislabel or weaken their accepted semantics, so this narrow
research adapter validates its own price basis and reuses public accounting.

The fixed logical material interval is [2016-01-01, 2024-01-01). All published
NYSE sessions in that interval are required for every symbol, at New York local
midnight in UTC representation. No missing session is imputed. The existing
published-session authority is reused; its complete history is calendar metadata,
not 2024+ price data. Acquisition uses only an explicitly injected transport;
there is no network or credential implementation in this profile. The public
`build_alpaca_request()` maps the half-open interval to the provider
inclusive end `2023-12-31T23:59:59.999999Z`; `parse_alpaca_page()` validates
bounded official JSON with exact Decimal prices. `AlpacaPageTransport` receives
an explicit request-to-bytes sender; tests supply fake bytes exclusively.
Pagination,
universe, request semantics, coverage and canonical data are checked before a
complete dataset can be written. A later separately reviewed operator adapter
owns any real credentials and acquisition. No 2024+ bars may be acquired or read.

The documented multi-symbol response requires the top-level `bars` and
`next_page_token` fields. The provider-optional top-level `currency` field is
accepted when present only when it is exactly the frozen requested `USD`;
responses without it remain valid. Every other top-level field is rejected.
This response-shape compatibility rule does not change the frozen request,
price basis, adjustment, feed, asof, date bounds, pagination, or dataset
identity contract.

## Frozen strategies and timing

Three MA pairs: 35/50, 55/100, 50/200. Thirty configurations use one MA pair and
zero or one confirmation policy. Canonical order is family order below, declared
MA-pair order above, then parameter order below. No stacking, expressions,
automatically generated combinations, new thresholds or expanded MA grid.

| Family | Entry with bullish fast > slow state | Exit |
| --- | --- | --- |
| BASE_MA | No further confirmation | fast < slow |
| MA_PERCENT_BAND | fast > slow*(1+band), band .005/.010/.015 | fast < slow*(1-band) |
| MA_ADX / parameter "20" (ADX20) | Wilder ADX(14) >= 20 | fast < slow |
| MA_ADX / parameter "25" (ADX25_RISING) | Wilder ADX(14) >= 25 **and** current ADX > prior ADX | fast < slow |
| MA_DONCHIAN | latest completed close > prior 20 or 55 completed-session high | fast < slow |
| MA_LONG_MOMENTUM | completed 252-session return >0 OR separate variant close >=90% of prior 252-session high | fast < slow |

The MA band can confirm after an earlier ordinary crossover. It does not require
simultaneous crossing events. Equality is HOLD. ADX, channels and momentum never
block exits. Donchian and prior 252-session highs exclude the latest completed
bar; long-return comparison uses the close 252 completed sessions earlier.
Wilder ATR(14) is descriptive only; no ATR stops or directional admission.
Wilder true range/directional movement starts with the first adjacent bar pair;
ATR seeds from 14 true ranges, ADX from the first 14 DX observations.

At execution session N, signals/ATR use only completed data through N-1. Entry
and exit fill at N open with adverse slippage. N high/low/close cannot affect
that decision; N close values the resulting account. Indicators may use pre-2019
warmup; no account or position state carries across independent regimes.

## Economics and evaluation

Each symbol/configuration/regime owns an independent $100,000 virtual account.
Long only, no leverage, whole shares, 95% target allocation and 5% cash reserve.
Entry buys floor((cash*.95 - commission)/adversely slipped open), then passes
through existing RiskManager, OrderEngine and PaperLedger. Exit liquidates the
owned quantity through the same primitives. Every proposal/order/event/fill has
explicit UUID5 identities; default random identity factories are never used.
Base costs are $1/fill and 5 bps. Independent stress replay uses $2/fill and
10 bps without modifying the base result. Very small accounts that cannot buy
one share remain in cash. All proposed orders undergo deterministic risk checks.

Five fresh calendar regimes: 2019, 2020, 2021, 2022, 2023. One separate continuous
2019-01-01 through 2024-01-01 exclusive run. No reoptimization. This yields
1,200 independent regime cells and 240 continuous cells, each with base/stress
strategy and buy-and-hold evidence using the same price basis and economics.
Buy-and-hold buys at the first session open, then holds through the final close.
It includes entry costs and does not imply a costless index comparison.

Return is final marked equity/initial cash minus one. Drawdown is the worst
peak-to-trough decline across initial cash and session-close equity; intraday
risk is not inferred. Terminal positions remain marked, without a synthetic
end-date liquidation. Realized P&L includes ledger commissions. Closed trades
count liquidations; fills are separately retained. Turnover is gross executed
notional divided by average session-close equity. Time invested is the fraction
of execution sessions held after that session's opening decision. ATR retains
count/minimum/median/maximum absolute values and median ATR/completed-close.
No unsupported annualized, risk-adjusted or inferential metrics are fabricated.

## Aggregates, shortlist and neighbor evidence

Every configuration summarizes 40 independent symbol/year cells and eight
continuous symbol runs: positive/negative cell counts, minimum/median regime
return, worst/median regime drawdown, median regime turnover, positive continuous
symbol count, minimum/median continuous return and worst continuous drawdown.
All summaries are repeated for stress. Zero-return cells are neither positive
nor negative. Drawdown is a nonnegative loss fraction (lower is better).

The frozen lexicographic top 10 sorts by: more positive continuous symbols;
more positive regime cells; higher minimum continuous return; lower worst
continuous drawdown; higher median continuous return; higher median regime
return; lower median regime turnover; canonical configuration order.
Selection uses base evidence; stress is retained alongside it, not substituted.
This is descriptive selection, never qualification or a production binding.

Neighbors are adjacent declared MA-pair levels with identical filter and adjacent
numeric filter levels with identical pair. Endpoints list only existing
neighbors. The two momentum variants are distinct hypotheses, not numerical
neighbors. All neighbor results already belong to the frozen full grid; no new
runs or numerical robustness cutoff is invented. Review should consider broad
plateaus, isolated spikes, asset/regime dependence and cost fragility.

## Output and effect boundary

`filtered-trend-multi-asset-dataset/v1` and `filtered-trend-bundle/v1` are strict
canonical immutable JSON. UUID5 uses versioned typed semantic material, including
source HEAD/tree, exact dataset ID, price basis/provenance, universe, grid,
economics, regimes, candidate configurations, fills, metrics and trace identities.
No clocks, paths, UUID4, Python hashes, object identity or artifact bytes enter
research identity. Decimal calculations use a fixed 50-digit context.

The bundle retains all cells, continuous evidence, base/stress buy-and-hold,
aggregates, top-10 IDs and existing neighbor IDs. Readers independently validate
policy, complete topology, ledger fill accounting, result IDs, aggregates and
shortlist; they do not replay provider data or claim to verify omitted equity
traces. Trace semantic commitments are retained; full dataset is separate.
CSV and detached presentation models expose symbol/family/pair/filter,
regime/cross-asset evidence, buy-and-hold and cost stress. Existing P3 GUI behavior
is untouched; this checkpoint supplies models for later bounded GUI integration.

`qualification_policy=null`, `paper_binding=null`, `live_eligible=false` are
mandatory. No PAPER_CANDIDATE, P5 binding, P5 production state, broker, Robinhood,
live eligibility or FINAL_HOLDOUT authority follows.

After source acceptance/integration, a reviewed operator acquisition step must
supply this new dataset. Only then may the explicit offline command run:

```powershell
$env:PYTHONPATH='src'
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe scripts/run_filtered_trend_research.py --run --dataset <accepted-new-dataset.json> --output <fresh-report-directory> --expected-head <accepted-integrated-head> --expected-tree <accepted-tree>
```

The source-owned command checks clean integrated develop and local tracking
identity, performs no network/fetch and refuses existing output. Partial output
is preserved for review, never repaired or retried automatically. Return the
bundle, CSV and exact source/dataset identities for ChatGPT strategy review.
No real acquisition or production campaign runs during source work or CI.
