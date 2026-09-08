# PD2D1 First-Cycle Offline Market-Data Evidence

## Scope and provenance

This record freezes the offline market evidence used by PD2D1. The source page
label is **StockAnalysis SPY Historical Stock Price Data**, and that page
identifies **Tiingo** as its upstream data source. For this repository artifact,
the source is classified as `OFFLINE_SEED`, is explicitly non-authoritative,
and has source ID
`stockanalysis-tiingo-spy-daily-2026-08-v1`.

No value in this record mints C3 market-data authority. The selected
`2026-08-28` target bar remains the genuine selected C3 snapshot bar and was not
replaced by StockAnalysis/Tiingo or any other external evidence.

## Exact strategy-history source rows

```text
symbol: SPY

2026-08-21
  timestamp: 2026-08-21T20:00:00Z
  open:      Decimal("766.05")
  high:      Decimal("767.85")
  low:       Decimal("764.17")
  close:     Decimal("765.72")
  volume:    39188673

2026-08-24
  timestamp: 2026-08-24T20:00:00Z
  open:      Decimal("764.78")
  high:      Decimal("765.22")
  low:       Decimal("762.08")
  close:     Decimal("763.47")
  volume:    32430886

2026-08-25
  timestamp: 2026-08-25T20:00:00Z
  open:      Decimal("766.16")
  high:      Decimal("766.78")
  low:       Decimal("763.05")
  close:     Decimal("765.91")
  volume:    27422263

2026-08-26
  timestamp: 2026-08-26T20:00:00Z
  open:      Decimal("764.73")
  high:      Decimal("767.35")
  low:       Decimal("763.93")
  close:     Decimal("766.08")
  volume:    28751592

2026-08-27
  timestamp: 2026-08-27T20:00:00Z
  open:      Decimal("768.50")
  high:      Decimal("772.36")
  low:       Decimal("767.16")
  close:     Decimal("771.10")
  volume:    34557064
```

The external historical source is date-granular. `20:00:00Z` is an explicit
artifact normalization for these August 2026 XNYS sessions, corresponding to
modeled `16:00 America/New_York` regular-session close. It is not a
source-supplied timestamp.

## Canonical strategy-history artifact

```text
repo-relative path: docs/validation/evidence/pd2d1-spy-strategy-history-seed-2026-08-28.json
expected absolute transport path: F:\AI\worktrees\ai-trading-bot-personal-desktop\docs\validation\evidence\pd2d1-spy-strategy-history-seed-2026-08-28.json
seed_id: 5dc95e10-ba22-5b91-94b2-0d851aa8e2d7
SHA-256: 40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64
byte length: 1060
symbol: SPY
sessions: 2026-08-21, 2026-08-24, 2026-08-25, 2026-08-26, 2026-08-27
source classification: OFFLINE_SEED
source authoritative: False
source_id: stockanalysis-tiingo-spy-daily-2026-08-v1
target session: 2026-08-28
strategy config: short_window=3, long_window=5, desired_quantity=Decimal("1")
```

The exact artifact bytes are the direct output of
`serialize_strategy_history_seed(...)`. Rereading those bytes and calling
`verify_strategy_history_seed(...)` for `SPY`, target session `2026-08-28`,
the `3/5/1` strategy config, and the bound XNYS calendar returned successful
target-specific verified evidence. Parse/serialize replay was byte-identical,
and an independent SHA-256 and byte-length calculation matched the verified
evidence.

## Next-session open reference

```text
symbol: SPY
session: 2026-08-31
caller_asserted_open_reference_price: Decimal("767.33")
```

The caller-asserted open reference comes from the same StockAnalysis/Tiingo
historical evidence set. It is offline historical evidence only, is not a C3
artifact value, and grants no market-data authority.

## No-effect statement

Artifact generation was pure and offline. It performed no network fetch, C1
acquisition, P2 selected-snapshot read, production mutex operation, Paper-v2
read or mutation, Architecture-67 execution, provider call, or broker call.
