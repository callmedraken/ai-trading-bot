# Architecture 136 / GUI-A15 — Read-only Supervisor, Research & Strategy Governance

## Scope and source boundary

A15 is presentation-only. Branch `feature/gui-supervisor-research-governance`,
worktree `F:\AI\worktrees\ai-trading-bot-gui-supervisor-research-governance`.
Exact base HEAD `43899b2014fe452f921c2f320a2f8d0c2a26b817`, TREE
`ad2b2b980927d77d86b52e270d9a5c259f676c31`. This docs-only descendant closes
accepted A14 source HEAD `c29bb678dd7c64a317de602b81ba9df0aa8e1bd8`, TREE
`921b7b32bbfecbb454acc8916faa4362464b19d3`, GUI CI 38325919046 SUCCESS and
repository CI 38326059553 SUCCESS. A15 source acceptance requires subsequent
exact GitHub source/CI review by ChatGPT.

Frozen R1/R2 remain `6bf8753b0cc8950ae27b32b6858b64d454c512f0` and
`2f122958366d1db282fea51abbd461b83fa893d9`. No D1 operation is performed.

## Explicit inspection boundary

Normal startup adds exactly one optional input:
`--production-strategy-contract PATH`, stored as optional `pathlib.Path` in
`GuiStartupConfiguration` and consumed before Qt argument forwarding.
Absence instantiates no strategy reader and performs zero strategy evidence I/O.
Only explicit local JSON files are supported; UNC/device paths, URI/ADS syntax,
control characters, unsupported suffixes and drive-relative paths fail closed.
No environment, directory, latest-file, Git or filesystem discovery is used.

`ProductionStrategyContractInspectionService` opens the selected artifact in
binary read-only mode at most once, reads at most 16 KiB + one rejection byte,
decodes strict UTF-8 and passes the exact unmodified text to
`trading_bot.strategies.production.ProductionStrategyContract.from_json()`.
The existing `production-strategy-contract/v1` parser owns canonical JSON,
duplicates, exact fields, deterministic identity, source hashes and config
semantics. The GUI does not duplicate that schema or compose production runtime.
Success and failures are cached. Diagnostics are fixed closed messages.

The immutable GUI view retains only UUID/date, bounded lowercase HEAD/TREE,
closed strategy/version, bounded symbol/windows and exact positive Decimal.
Window counts are 1..1,000,000; fixed-point quantity representation is bounded
to 128 characters. These presentation bounds grant no strategy authority.
No path, raw JSON, exception, provider material or authority object survives
acquisition. No production strategy object is retained in the view.

## Pure composition and presentation

MainWindow acquires exactly eight application-service states, once and in order:
overview, research, paper, paper-account, market-data, operations, runtime,
production strategy. Overview uses the same cached strategy/runtime results;
startup research acquisition is cached so Overview adds no duplicate report read.

`build_supervisor_state()` receives only already-acquired ResearchPageState,
RuntimePageState and ProductionStrategyPageState. It performs no reads or service
calls. Canonical research UUIDs are copied without report source paths/messages.
A loaded historical report proves evidence availability, never process liveness.
Recorded D1 status is explicitly labeled RECORDED; it is never current D2 state.
D2 supervisor connection is always visibly **Not connected**.

Consistency is NOT_CHECKED unless both an accepted strategy contract and recorded
D1 session exist. It compares exactly contract ID, HEAD, TREE and target session.
All equal yields CONSISTENT; any difference yields CONFLICTING / ATTENTION and
a fixed explanation. No reconciliation/repair is attempted. Qualification/ACL
identities are not added to this comparison. Existing Runtime ATTENTION remains
attention. Valid contract and/or recorded evidence yields informational AVAILABLE;
absence is UNAVAILABLE. Malformed selected strategy yields ATTENTION.

Supervisor renders plain selectable text in a vertical scroll area, including
long identities and hashes, usable at the 920x620 MainWindow minimum without
horizontal overflow. Stable pages are home, research, paper, paper-account,
market-data, operations, runtime, supervisor, evidence, system. No effect
buttons or polling are added.

Overview maps Supervisor UNAVAILABLE/AVAILABLE/ATTENTION to
UNAVAILABLE/INFO/BLOCKED. System receives the already-built Supervisor state,
maps it to UNAVAILABLE/AVAILABLE/BLOCKED and propagates BLOCKED to overall
ATTENTION. Safe audit identifiers are production contract ID/HEAD/TREE only.

Evidence adds one SUPERVISOR entry only for a valid selected contract:
"Production strategy contract", identifier contract_id, occurred_at=None.
The contract has a target date, not an event timestamp. Static governance,
derived consistency and disconnected D2 do not generate events. A11 filtering,
A12 System->Evidence and A13 Evidence->Supervisor use closed maps, with zero
service/file rereads on navigation. Existing pure System/Evidence callers may
omit the optional Supervisor parameter; normal startup always supplies it.

## Governance and future D2 design

Automatic promotion is disabled; human promotion is required; promotion authority
is disconnected; research cannot replace production. These are immutable fixed
presentation facts, not a promotion service. Research evidence may inform future
strategy review. It cannot replace the production strategy automatically.

A15 creates no canonical research candidate or promotion artifact, lifecycle,
AI approval, production-contract mutation or promotion command. The future
research lane retains ownership of canonical candidate evidence.

TARGET D2 DESIGN ONLY: PC ON -> supervisor reconciles current reality;
research may remain operational while trading waits; research never self-promotes.
RECONCILE, PREMARKET_WAIT, TRADING, NEXT_SESSION_WAIT and BLOCKED are future
design vocabulary only. A15 implements no D2 supervisor/effects.

## CI and inventory

Only dedicated GUI workflow push selection becomes `feature/gui-*`.
Windows/Python 3.14, `.[dev,gui]`, real PySide6, complete tests/gui, combined
non-mutating Ruff and diff checks remain. Repository checkpoint push allowlist,
ACTIVE_CI_CHECKPOINTS and production checkpoint/profile mapping remain unchanged.
Fresh repository dispatch follows successful dedicated GUI CI. Missing runs are
never PASS. Source acceptance remains ChatGPT-owned.

Source inventory: GUI 44, ACTIVE 62, FULL 169, ROBINHOOD 94, LEGACY 215,
EXHAUSTIVE 384. GUI remains legacy under Architecture 132; A15 does not
reclassify it. Only directly stale current count assertions and their three
test-file blob pins are updated; executable/native/AST pins remain unchanged.

## Capability freeze

```text
DIRECT_PRODUCTION_SQLITE_ACCESS=False
PRODUCTION_SQLITE_WRITES=False
CREDENTIAL_MANAGER_ACCESS=False
ALPACA_NETWORK_ACCESS=False
ROBINHOOD_NETWORK_ACCESS=False
SCHEDULER_ACCESS=False
ACL_MUTATION=False
PAPER_EXECUTION=False
BROKERAGE_ACCESS=False
FILESYSTEM_DISCOVERY=False
LATEST_EVIDENCE_DISCOVERY=False
RESEARCH_EXECUTION=False
AUTOMATIC_STRATEGY_PROMOTION=False
HUMAN_PROMOTION_REQUIRED=True
PROMOTION_AUTHORITY_CONNECTED=False
CAN_RESEARCH_REPLACE_PRODUCTION=False
D2_SUPERVISOR_EXECUTION=False
EXPLICIT_PRODUCTION_CONTRACT_ONLY=True
SERVICE_REREADS_ON_NAVIGATION=0
FILE_REREADS_ON_NAVIGATION=0
```
