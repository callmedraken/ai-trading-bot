# Architecture 152-PM1 — Account-aware Portfolio Manager foundation

## Status and scope

PM1 is a source-only foundation for a separate, longer-horizon Portfolio Manager
desktop profile. It adopts an existing portfolio, builds auditable research
recommendations, evaluates them through independent deterministic risk rules,
and displays preview-only plans. It is not a trading authorization or a
validated profitable strategy. The feature branch is
`feature/robinhood-portfolio-manager-current`; its reviewed base is develop
`e578a7ff0e128a1f9895a9df82296f73f550e9c5` / tree
`f6b3036c00afebfce93a1500731e504edba954d4`. PM1 was subsequently
SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at
`0fc38b187169ce2322bca108751b4c05fe4078c0` / tree
`17426689d0eb381491654bb03caa28e0b29899ea`; feature FULL run
`45954491120` and develop exact-reuse run `45956617137` are terminal
SUCCESS. This terminal source status does not grant trading authority.

PM1 keeps the Portfolio Manager's account fingerprint, durable namespace,
decision history, synthetic execution state, research provider, and risk policy
separate from the intraday product. It does not assume the current intraday
account is the intended PM account. Account selection requires an explicit
eligible fingerprint; ambiguous account discovery remains blocked.

## Ownership and data flow

The current implementation is grouped under `src/trading_bot/portfolio_manager/`:

- `models.py` owns immutable account-binding, position, order, observation,
  coverage, condition, and deterministic financial identity types. Decimal
  canonicalization and arithmetic avoid dependence on ambient context.
- `observation.py` owns account binding, adoption, and injected provider
  parsing. An observation preserves known and unknown facts, including
  fractional quantity, sellable quantity, average cost when available, quotes,
  cash, broker-reported equity, local valuation, order coverage, and
  reconciliation conditions. Missing costs and chronology are not fabricated.
- `adapters.py` bridges to the existing strict `PortfolioState` only when the
  observation is fully valued, account matched, positive long holdings have
  known positive average cost, and there are no blocking stale, incomplete, or
  reconciliation conditions. Cash-only, unknown-cost, stale, mismatched, and
  incomplete observations remain valid observation facts and are not coerced
  into a strict optimizer state.
- `decision.py` defines the typed `DecisionProvider` boundary and deterministic
  synthetic and fake injected providers. A recommendation binds snapshot,
  account, research, strategy/version, decision time, horizon, action, target,
  rationale, and uncertainty/evidence status. A recommendation is not an order.
- `risk.py` independently checks account and snapshot identity, freshness,
  data completeness, supported long-only positions, sellable quantity, pending
  orders, cash and unleveraged buying power, fees/slippage, and configured
  concentration/exposure limits. It does not assume proceeds from a proposed
  sale are available to a buy.
- `planning.py` builds dependency-ordered preview legs. Approved sells precede
  buys, buy legs depend on the approved sell legs, and proposed sale proceeds
  remain zero available. Plan and leg values are immutable and explicitly
  preview-only with dispatch unauthorized.
- `store.py` owns account-namespaced durable decision and intent history with
  semantic uniqueness and conflict detection.
- `application_service.py` composes observation, research, decision, risk,
  preview planning, worker lifecycle, cached state, and restart recovery. It
  reuses `live_prototype.application_service.DesktopWorkers` for thread/event
  ownership while providing PM-specific observation and research workers.
- `synthetic_demo.py`, `application.py`, and `window.py` provide the synthetic
  desktop composition and presentation boundary. The GUI reads cached worker
  state; provider and research work stay off the Qt UI thread.

The intended flow is:

```text
account selection -> adopted observation -> research -> recommendation
  -> independent risk evaluation -> preview-only plan -> durable outcome
```

## Reused foundations and explicit adapters

| Existing foundation | PM1 use | Boundary |
| --- | --- | --- |
| `desktop_paper.robinhood_read` and `robinhood_mcp.parsing` | Reuse accepted typed account, portfolio, position, order, and quote parsing. | The account/order window remains bounded; no undocumented endpoint or real read is invoked. |
| `robinhood_mcp.current_read_transport` | The fake end-to-end test injects an in-memory SDK session through the existing read transport. | Default application composition uses a synthetic observation source and does not create a transport session. |
| `portfolio.models.PortfolioState` | `adapters.to_portfolio_state` converts only fully valued, supported, long, bound, consistent observations with positive known average cost. | Cash-only, unknown-cost, stale, incomplete, or mismatched observations remain typed observations and do not get fabricated into the strict optimizer model. |
| `risk.models.RiskLimits` | PM policy validates compatible concentration, reserve, order-notional, and commission bounds. | The ledger `RiskManager` is not forced onto observation-only state requiring timestamped ledger positions; PM risk evaluation is a separate deterministic boundary. |
| Arch149 replay | The adapter verifies the public replay identity and translates target outputs into diagnostic signals. | No private ranking code, fills, performance, default provider selection, or execution authority is shared. |
| `live_prototype.application_service.DesktopWorkers` | Reuse its generic thread/event startup and ownership for monitoring and research workers. | PM state, polling, stop/restart semantics, durable history, and cached view remain PM-specific. |
| PySide6 | A compact new PM window presents cached service state and manual lifecycle controls. | The legacy pre-Robinhood GUI and its retired runtime remain legacy; PM1 does not add broker-integrated presentation. |

Observation completeness and order visibility are distinct. Robinhood
agentic-order observations remain explicitly bounded and cannot be relabeled as
account-wide reconciliation. Incomplete observations can be displayed while
the affected financial actions remain blocked. External holdings, cost-basis
changes, outstanding orders, stale/missing prices, unsupported assets, short
positions, account mismatch, pagination faults, and unknown ownership remain
visible conditions.
The accepted read surface supplies equity positions; an unsupported asset is
visible only when the provider supplies an asset-kind hint. PM1 does not claim
complete non-equity or all-account order coverage.

The worker lifecycle follows the current desktop invariant: owner-controlled
manual Start and Stop, independent monitoring and research workers where
compatible, no new preview dispatch after Stop, recovery of synthetic work,
and no forced liquidation of existing holdings. The GUI displays
`SYNTHETIC / DISARMED`; there is no live-placement method. The application does
not self-update, register a scheduler, start unattended at login, or mutate
production state.

The PM1 synthetic window is a new observation-only product profile. It does
not reclassify or reactivate the legacy pre-Robinhood GUI tied to the retired
runtime model, and it does not provide a Robinhood-integrated GUI.

## Architecture 149 integration boundary

`arch149_adapter.py` consumes only the public, identity-verified
`RotationReplay.targets` from the frozen
`MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1` implementation. It exposes typed
signal facts in frozen universe order while retaining the replay and target
sequence identities. The adapter marks them `UNADMITTED` and
`RESEARCH_SIGNAL_ONLY_NO_ORDER_AUTHORITY`; performance evidence is unavailable
to PM1 and order authority is false. It does not export replay fills, returns,
daily marks, or a second ranking implementation, and it is not selected by the
default application composition.

The source-owned exploratory record is
`8a3d7c3a-d2f9-5f10-91e6-ba06c3935d84`, SHA-256
`69f941721aaba736cef45b80543f7a238a30dcdb74f03c046c3fc01aabb5dbcf`,
classified `EXPLORATORY_CANDIDATE_ONLY`. The PM adapter leaves this identity
and classification unchanged.

The adapter test constructs only synthetic in-memory bars within Arch149's
accepted 2016–2023 input boundary. It does not access 2024–2026 confirmation
data. The monthly single-ETF strategy remains distinct from general
multi-holding portfolio management. Preserve Arch149's candidate classification
and confirmation firewall; PM1's adapter does not alter or admit its evidence.
The frozen strategy's 12-minus-1-session ranking, eight-symbol universe,
month-end signal, next-session OPEN, 95% allocation, cost assumptions, and
confirmation thresholds remain solely owned by the Arch149 implementation and
its validation record.

## Certification ownership and authority ceiling

The source-only checkpoint is `arch152-portfolio-manager-foundation`, mapped
to the existing `full` profile. PM1 tests are owned by the whole
`tests/portfolio_manager/` directory in `FULL_DIRECTORIES`; new modules in that
directory are classified through directory ownership. The frozen 122-module
FULL and 49-module Robinhood required baselines, seven deterministic nonempty
`broad-1`–`broad-7` lanes, and 300-second per-lane ceiling are unchanged. No
module-count or lane-size pin is introduced.

The checkpoint registers source tests and routing only. It has no preflight,
execution callback, head override, credential access, real provider invocation,
broker action, order route, cancellation, or production mutation. Mapped
canonical FULL is GitHub-owned. The latest successful comparable baseline at
the reviewed base was run `45919230088`: 18,566 passed, 10 skipped, slowest lane
282.020 seconds (broad-1 258.979 seconds). PM1-focused tests are kept small to
preserve the existing timing headroom.

No source checkpoint grants Robinhood/OAuth access, live eligibility, paper or
live execution, credential authority, Arch149 admission, real AI-provider
access, protected data access, or access to sealed 2024+ evidence. PM1's source,
certification and integration gates are closed, but it remains a
synthetic/disarmed operational foundation. Read-only real-account coverage is a
separate PM2A qualification, and execution authority remains a later separately
reviewed boundary.
