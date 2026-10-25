# AI Trading Bot — Current Handoff

## Current integrated source

Current develop before this Architecture-146 design checkpoint:

    HEAD a637f1b34565a715c14874d0f9a9686388319c16
    TREE e870cc8f28138076d1e247eb92358d88a89c2f26
    docs-only Source Gates #716 / 40169845896 attempt 1: SUCCESS

The preceding fresh-successor source is accepted/integrated at
b18c6e32606828beeebc540a93c9f05e3e024323 /
b082c15bc697bf289fc7997b3d7bf87050082dc3. R1 is reconciled and permanently
consumed. Preserved incident releases remain immutable/untrusted.

## Architecture 146 design decision

The attempted weekend offline robustness diagnostic correctly stopped before
research because no approved local historical dataset exists. The repository
data directory is empty and repository CSV files are fixtures/examples.

Architecture 146 — Historical Research Data Custody and Partition Contract is a
documentation-only accepted design. It is separate from Architecture 145-B.

v1 research data is frozen as:

    symbol      SPY
    vendor      Alpaca Market Data API
    bars        /v2/stocks/SPY/bars
    timeframe   1Day
    adjustment  raw
    asof        -
    feed        sip
    currency    USD
    sort        asc
    pagination  complete

Same-vendor corporate actions are mandatory provenance from
/v1/corporate-actions for SPY.

Frozen chronological roles:

    DEVELOPMENT  [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z)
    WALK_FORWARD [2020-01-01T00:00:00Z, 2024-01-01T00:00:00Z)
    FINAL_HOLDOUT[2024-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

Development-visible root:

    F:\AI\ai-trading-bot\data\research\arch146-v1

It may contain only vendor/open bytes, normalized OPEN SPY.csv and non-price
holdout commitments. OPEN contains DEVELOPMENT + WALK_FORWARD only.

Future physical holdout custody root:

    F:\AI\research-holdout\arch146-v1

The design requires a protected Administrators+SYSTEM-only DACL when that root is
later created under separate host authority. No root/ACL/data exists merely
because the design names it.

## Critical compatibility finding

CSVHistoricalDataProvider validates the complete CSV before request filtering, so
a mixed open+holdout CSV is forbidden for development.

Architecture 145-A also binds one logical historical_data_fingerprint across all
three partitions. Current physical partition fingerprints differ because request
bounds and OHLCV are fingerprint material. Do not rewrite 145-A or pretend the
UUIDs are interchangeable.

Architecture 146-A must add an immutable additive dataset snapshot/partition
manifest layer that externally proves OPEN + HOLDOUT membership in one logical
snapshot, preserves each physical partition's own fingerprint, and supplies a
privileged full logical fingerprint for later Architecture-145 policy lineage.

## No-effect boundary

This design does not authorize:

- provider/network or credential access;
- data acquisition/import;
- creation of either data root;
- holdout reads;
- ACL mutation;
- backtests/campaigns;
- Architecture 145 holdout admission or eligibility;
- Architecture 145-B;
- production deployment/effects;
- paper/broker/live effects.

No production deployment generation is frozen during the weekend.

## Next owner / next step

Next source checkpoint:
**Architecture 146-A — historical research dataset manifest and partition
enforcement**.

Use a new feature worktree from the then-current terminal-green develop tip. It
is pure/source-only with synthetic fixtures. Add deterministic canonical
manifest/snapshot models and external verification. Do not call Alpaca, use real
credentials, create F:\AI\research-holdout, inspect real holdout data, run a real
backtest, modify Architecture-145 schemas or start 145-B.

After one atomic publication and terminal CI, ChatGPT performs exact-source
review. Real data acquisition remains a separately reviewed future 146-B
checkpoint.

Sunday night remains the production-mode transition: freeze only the then-current
terminal-green develop tip for the fresh deployment-admission sequence.
