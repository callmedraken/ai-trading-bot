# Architecture 148-B1 — Intraday Data and Backtest Contract

Status: **CURRENT SOURCE CONTRACT / FAKE-ONLY VALIDATION.** This document does
not constitute exact-source acceptance or authorize a provider observation,
credential access, broker action, B2 or holdout access.

## Frozen data scope

- Partition: OPEN, `[2016-01-01, 2024-01-01)` UTC.
- Symbols, in canonical order: `QQQ`, `TQQQ`, `SQQQ`.
- Timeframe: `5Min`.
- Adjustment: `all`.
- Feed: `sip`.
- Currency / price basis: `USD` /
  `ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1`.
- `FINAL_HOLDOUT` begins at 2024-01-01 and remains sealed. B2 is not authorized.

The accepted Architecture-146 authority is
`nyse-published-regular-sessions-2016-2026-v1`, digest
`7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1`, source
bundle SHA-256
`6db5b3c039dc98e6a21d5dc8e917de60305c919ea6fdf4cc8b8141185b774607`, and
source-manifest SHA-256
`e1f9f6f0048114f2307255a7fa1b40c3661c115c1e8cc22c992246207e084735`. It
commits published session dates; it does not commit Architecture-148's
projected intraday open and close times.

## Architecture-148 schedule commitment

Schedule schema: `arch148-intraday-session-schedule/v1`.
Identity version: `arch148-intraday-session-schedule-identity/v1`.
Identity: `4fe981d0-34ef-57be-a7d1-ffd017460bf5`.
Canonical-material SHA-256:
`a33be70499cdafbfa21f45a04c854ab834425807b6c0314814b7442749aa2bad`.

The immutable commitment binds the upstream Architecture-146 identity, digest,
source bundle and source manifest; timezone `America/New_York`; regular open
09:30 ET; regular close 16:00 ET; early close 13:00 ET; and exactly these
2016-2023 early-close dates:

- 2016-11-25
- 2017-07-03, 2017-11-24
- 2018-07-03, 2018-11-23, 2018-12-24
- 2019-07-03, 2019-11-29, 2019-12-24
- 2020-11-27, 2020-12-24
- 2021-11-26
- 2022-11-25
- 2023-07-03, 2023-11-24

No other dates are modeled as early closes by this projection. The
Architecture-148 dataset and custody evidence each bind the schedule identity
and digest in both their semantic identities and serialized forms. Parse and
reconstruction reject either value when it differs from the frozen
Architecture-148 commitment; the Architecture-146 date authority alone cannot
substitute for it. Dataset and custody serialization use
`arch148-intraday-dataset/v2` and `arch148-intraday-custody-evidence/v2`, with
the corresponding v2 semantic identity versions.

## Backtest execution contract

Signals use completed bar N. An entry may fill no earlier than bar N+1 OPEN,
with configured buy slippage. This remains a no-lookahead rule and does not
permit a signal fill based on N+1 OHLC.

Immediately after the N+1 entry fill, the fixed 3% protective stop becomes
active for the remainder of that bar. Its threshold is derived from the
simulated reconciled entry fill. If the entry-bar OPEN is at or below the
threshold, the stop exits at OPEN. Otherwise, if LOW reaches or crosses the
threshold, the stop exits at the threshold. The same transaction cost and
slippage model applies to the stop sell.

A same-entry-bar stop increments stop-hit count, records `exit_reason=STOP`,
may have `entry_at == exit_at` and zero holding duration, and leaves the
simulator FLAT. It cannot cause another entry in that cycle/bar. The stop keeps
priority over regime and scheduled forced-flat exits. Regime and scheduled
forced-flat exits otherwise use the next bar OPEN.

## Focused regression surface

The source regression suite is in:

- `tests/experiments/test_arch148_intraday.py`
- `tests/live_prototype/test_arch148_runtime.py`
- `tests/live_prototype/test_application_composition.py`

It covers exact schedule dates, representative daylight/standard-time UTC and
local instants, published non-session dates, schedule identity/digest
roundtrips and rejection, no substitute from the date authority, entry-bar stop
threshold/gap/carry behavior, same-cycle re-entry prevention, stop priority, and
the shared two-completed-bar regime-exit rule. All source checks use fake data;
they do not read provider credentials or issue provider/broker requests.
