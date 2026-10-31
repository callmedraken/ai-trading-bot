# Architecture 147 — Single-user desktop product pivot

Status: CURRENT product roadmap; P2/P3 accepted and real-run complete; P4 accepted with runtime smoke complete; P5 architecture/design current.

## Product contract

The product is a private, single-user Windows desktop trading bot. The trusted
machine owner, Administrator, SYSTEM, and physical owner are outside the
application threat boundary, as reaffirmed by Architecture 102. Production
quality for this product means correct deterministic decisions, reconciliation,
duplicate-effect protection, safe restart behavior, stale-data rejection,
credential isolation, paper/live separation, explicit live arming, limits,
audit, health, kill-switch, backup, recovery, and reliable long-running
operation. It does not require hostile-Administrator namespace ceremony.

The user explicitly starts and stops the application. After Start, trading and
research workers may run unattended until Stop. The application never updates
its own source or executable tree. The manual update sequence is:

    user Start -> workers run unattended -> user Stop -> reconcile/close
      -> manual update while stopped -> checks/migration -> user Start

An approved checkout or simple versioned directory may be used for a stopped
manual update. No STAGE->ACTIVE, ACTIVE->ARCHIVE, rename/promotion, junction
swap, scheduler rebind, or immutable-release publisher is a current product
prerequisite. Task Scheduler/start-at-login may be added later as convenience.
State and credentials remain outside disposable source files.

The bot owns strategy decisions, research, portfolio targets, deterministic
`RiskManager` decisions, exact order intent, operating mode, live arming, local
limits, reconciliation, audit, and the kill switch. Robinhood's official MCP /
Agentic Trading surface is the future brokerage transport and execution
boundary. It is not strategy authority and may not bypass local risk or choose
a different order. P1 enables no real mutation, OAuth, account query, order
review, order placement, paper effect, broker effect, or live effect.

## Roadmap

    P1  desktop research simplification
    P2  one real SPY acquisition + verification + freeze
    P3  real optimizer / walk-forward campaign + Research Results GUI
    P4  long-running desktop supervisor with concurrent trading + research workers and GUI Start/Stop
    P5  unattended synthetic/forward paper soak using existing Robinhood MCP review/quotes/history/account foundations
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production maturity / soak / monitoring / backup / restart / reconnect / credential rotation

Trading and research may operate concurrently after P2. Paper trading remains
the default and LIVE remains disabled until separately reviewed gates are met.
The existing Research Results GUI is reused and audited in P3; GUI rebuild is
not a P1 blocker.

## P1 desktop research profile

P1 keeps the Architecture 146-A deterministic dataset contracts and identities:

- `HistoricalResearchPartitionManifest`;
- `HistoricalResearchDatasetSnapshot`;
- `HistoricalResearchPartitionRole`;
- normalized CSV canonicalization and full historical fingerprint semantics;
- `SPY`, `XNYS`, `1Day`, `RAW`, `SIP`, `USD`, `PRICE_RETURN`;
- the existing partition boundary at `2024-01-01`;
- published session authority `nyse-published-regular-sessions-2016-2026-v1`;
- 2718 sessions, digest
  `7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1`.

Those values are not repinned because storage changes. The model's two extra
closures, 2018-12-05 and 2025-01-09, remain part of the existing historical
authority reconciliation.

The source-owned fixed production root is:

    F:\AI\ai-trading-bot\data\research\desktop-v1

Its conceptual layout is explicit and ordinary:

    desktop-v1/
      raw/bars/
      raw/corporate-actions/
      normalized/open/SPY.csv
      normalized/holdout/SPY.csv
      corporate-actions/sidecar.json
      manifests/open.json
      manifests/holdout.json
      manifests/snapshot.json
      acquisition.json

Tests inject a temporary root only through the explicit test seam. The desktop
profile creates directories/files normally, rejects arbitrary production-root
substitution, refuses to overwrite completed files, writes and fsyncs bytes
where practical, validates readback/digests and manifest membership, and keeps
incomplete or partial acquisition state visible. It performs no automatic
destructive cleanup. It has no ACL, SID, SDDL, token, elevation, `ctypes`,
`Set-Acl`, ownership, alternate-principal, protected-parent, claim-ceremony,
rename/promotion, or junction/symlink-publication dependency.

The shared acquisition kernel now receives a small profile-owned persistence
adapter. The current desktop adapter owns ordinary inspection and verification;
the preserved protected `CustodyInspection`/`CustodyPersistencePlan` remains a
separate legacy/deferred adapter. The desktop adapter never reports
Administrator/SYSTEM custody under new names and does not weaken or retry the
old protected path.

## Research data boundaries

The current OPEN loader reads only normalized OPEN bytes plus the required
non-price manifests and corporate-action sidecar. It validates exact bytes,
size, hashes, canonical CSV, snapshot/manifest membership, and the accepted
published session authority. It does not read normalized FINAL_HOLDOUT bytes,
raw full-range vendor pages, or require `ACCEPTED_CUSTODY_ADMISSIONS` or a
protected-host report.

The explicit final-holdout loader is a separate boundary. It requires the exact
existing Architecture-145 `ResearchStrategyFinalHoldoutAdmission` type and
validates its policy, dataset, and partition binding against the desktop
snapshot before returning the FINAL_HOLDOUT data. It revalidates the complete
OPEN + FINAL_HOLDOUT physical dataset and frozen fingerprint commitments. The
ordinary optimizer, walk-forward, and candidate-selection modules do not import
or call this loader. This is a software-use boundary, not a claim that the
trusted machine owner cannot inspect files.

P2 uses fake transport/credentials in tests. Its accepted bridge performed the
separately reviewed real acquisition after source acceptance/integration. That
operation is never executed by implementation, admission or CI. P3 uses OPEN only.

## P2 desktop interactive acquisition bridge

P1 is accepted/integrated at `e8817e0214074b03d3d9ecd73232b7a2379276b9`:
feature #807 canonical FULL and develop #808 succeeded; develop reused the
exact feature certification. Failed #806 remains immutable and was not rerun.

`scripts/acquire_desktop_research.py` requires `--execute`, `--expected-head`
and `--expected-tree`. No request/root/partition override exists. Before any
write or prompt it verifies the canonical project root, develop branch, exact
reviewed HEAD/tree, `git status --porcelain=v1 --untracked-files=no`, canonical
origin URL, and local origin/develop equality. It then verifies the accepted
published authority and requires the fixed desktop root absent. Ordinary
exclusive root creation and `DesktopResearchStorage` preparation precede input.

`DesktopInteractiveResearchCredentialSource` is one-use, binds exact expected
HEAD/tree and accepted authority through the shared kernel's bind hook, and
uses only the reviewed `interactive_research_credentials()` hidden prompts.
It has no persistence, environment/config/file fallback, token/SID/elevation
observer or Credential Manager requirement. The historical
`EphemeralHistoricalResearchCredentialSource` and `AcceptedB2Preflight` remain
unchanged and are not used by this path.

The shared `HistoricalResearchAcquisitionOperator` and existing
`HttpsHistoricalResearchTransport` own the frozen requests, pagination,
normalization and deterministic identities. Alpaca historical Market Data is
the research-data source only; Robinhood MCP / Agentic Trading remains the
future brokerage execution/account boundary. No brokerage/order adapter is
introduced. Requests remain SPY, 1Day, 2016-01-01T00:00:00Z through
2026-10-24T00:00:00Z, raw/SIP/USD/ascending/10000 bars and the existing full-range
US complete corporate-actions request with ascending/1000 pagination.

After acquisition the bridge saves the kernel evidence as `evidence.json`.
`inspect_desktop_dataset_integrity()` verifies COMPLETE, reconstructs canonical
evidence, manifests and snapshot, reads OPEN/FINAL_HOLDOUT physical bytes and
bars raw digest vector, checks corporate raw pages against the original sidecar
and commitments, and invokes `verify_desktop_published_dataset()` against the
accepted 2718-session authority and full fingerprint. It returns an immutable
summary of profile, source/attempt/dataset/manifest/authority identities,
row counts/endpoints and SHA256 values, never OHLCV or bars. This read-only
inspection is not strategy holdout admission. Normal research continues through
`load_desktop_open_research()`; strategy FINAL_HOLDOUT access still requires
`ResearchStrategyFinalHoldoutAdmission`.

Success prints compact sanitized JSON including both integrity and OPEN-loader
PASS. Failure prints only stage/classification, never exception text, response
bodies, credentials or lengths. Authentication/entitlement, rate-limit, server,
transport, response-shape, pagination/replay, validation, persistence,
preexisting destination and source mismatch failures remain distinct. No retry
or SIP fallback occurs. Any existing root, including partial/empty state, stops
a later invocation; recovery is deferred to a later reviewed action.

P2 source and real acquisition are accepted. Exact source, terminal CI,
both-attempt chronology and dataset commitments are frozen in the validation
document. The first consumed attempt stopped at CREDENTIALS with zero provider
requests/pages; exact read-only reconciliation preceded recovery. Successful
attempt: `a81baba7-7123-45eb-945d-9fb048e24607`. No old observer was retried.

## P3 offline campaign and Research Results integration

P3 source implementation was SOURCE-ONLY; its accepted real offline run is now
complete. Source tests, admission and GitHub CI never execute the production
campaign or open the production dataset. The source-owned single command
is `scripts/run_desktop_research_campaign.py --run`, invoked with the existing
venv Python after exact-source acceptance/integration. It requires clean main
develop and matching local origin/develop; it performs no fetch, network,
credential, provider, Alpaca, Robinhood, broker, scheduler, ACL or live operation.

`DesktopCampaignDatasetBinding` binds the exact accepted desktop-v1 acquisition
source HEAD/tree, attempt, published-session identity/digest, snapshot, full
historical fingerprint commitment, OPEN manifest/hash/count/endpoints,
corporate-action digest and acquisition evidence digest. Production cannot
substitute another desktop-v1 dataset or supply a binding override. Synthetic
tests have an explicit test-storage-only binding seam. Validation reads only
non-price commitments; `load_desktop_open_research()` alone reads prices.
Neither `load_desktop_final_holdout()` nor `inspect_desktop_dataset_integrity()`
is imported/called by the campaign, and normalized holdout CSV is never read.
P2 full physical integrity remains accepted evidence, not a campaign operation.

The source-owned v1 MovingAverageCrossover grid is short 5..60 step 5, long
40..250 step 10, short < long, ordered short then long ascending: **255** valid
configurations. Desired quantity is 100 shares. The explicit evaluation policy
uses 100000 starting cash, 1 fixed commission, 5 basis-point slippage, whole
shares, buying/selling enabled in the offline risk engine, 100% position/exposure
ceilings and no cash-reserve fraction. Missing modeled sessions are allowed
because P2 already proves published session coverage; no bar is fabricated.
`trading_enabled=True` is solely the existing offline risk flag, not external
trading authority. No margin, leverage or short position is introduced.

Development search uses only [2016-01-01, 2020-01-01). The accepted calendar
interprets request boundaries as New York dates; a source-owned additive
`nyse-local-year-boundaries/unchanged-open-bars/v1` request projection represents
January boundaries at New York midnight (05:00 UTC), preserving every P2 bar and
its timestamp/OHLCV. The projected request gets its own historical fingerprint.
No predecessor request, fingerprint or calendar semantics are changed. This
retains final December sessions that UTC-midnight request ends would exclude
from the engine's expected calendar range. The logical Development/WALK_FORWARD
separation is unchanged; no 2020+ session enters ranking.

Every grid configuration receives one retained development evaluation using
`ResearchStrategyDefinition`, `ResearchStrategyEvaluationPolicy` and the public
strategy-native backtest runner/verifier. Public verification independently
replays the engine, as its accepted contract requires. Evidence retains source,
definition/policy/data/run/result/evidence IDs, bars/endpoints, total return,
drawdown, final equity, measured fills, closed trades and PerformanceReport
turnover (executed notional / average equity). It is not relabeled historical
aggregate one-way turnover. Decimal computation uses a fixed 50-digit context.

Explicit ranking: total return descending, maximum drawdown ascending, then
canonical numeric (short, long) configuration ascending. The full rank and
top-32 shortlist are recorded before walk-forward; later observations never
alter either. The direct ranking projection avoids the historical comparator's
different metric model/tie semantics. The research-only leader is Development
rank 1, regardless of later test returns. It grants no lifecycle stage,
PAPER_CANDIDATE, paper/live eligibility, promotion or trading authority.

The accepted fold contract requires training_start < training_end == test_start
< test_end and each subsequent training_start == previous test_end. P3 preserves
it with two disjoint source-owned folds, expressed in New York calendar dates:

| Fold | Training [start, end) | Test [start, end) |
| --- | --- | --- |
| 1 | 2016-01-01, 2020-01-01 | 2020-01-01, 2021-01-01 |
| 2 | 2021-01-01, 2022-01-01 | 2022-01-01, 2024-01-01 |

This is not an expanding-window claim. 2021 is training only. Each fold side
starts with independent engine state; indicator warmup reduces test trading
opportunity and no development state leaks into a test. The two windows have
different lengths; their returns/median are descriptive and not annualized.
Only shortlisted candidates use public walk-forward execution/verification.
Per-fold return/drawdown/bar counts and evidence, plus minimum/median return
and maximum drawdown, are retained. No qualification policy is applied in P3;
qualification is explicitly null. A later frozen robustness policy owns that
decision; no thresholds are inferred from observations.

Sensitivity uses already-completed Development results at (short +/-5, long)
and (short, long +/-10). Each missing grid-edge/constraint neighbor is explicit.
It performs no additional evaluation and infers no robustness or objective.

`DesktopCampaignBundle` is immutable `desktop-research-campaign/v1` strict
canonical JSON with typed, versioned, length-framed semantic UUID5 identities.
Campaign identity binds source/dataset/grid/policy/folds/ranking; candidate IDs
bind campaign and configuration; bundle identity binds all semantic evidence.
No identity uses artifact bytes, clocks, UUID4, filesystem paths or object
identity. Canonical parsing validates complete grid/order, provenance, ranking,
shortlist, fold chain, summaries, sensitivity and identity without execution.
A deterministic 255-row CSV projection makes missing walk-forward cells blank.

Output is ordinary untracked reports beneath the fixed
`F:\AI\ai-trading-bot\reports\research\desktop-v1\<campaign-id>` directory.
It never uses a runtime database, qualification temp root or protected 146 root.
Create-only candidate files carry semantic result IDs, fsync/readback, and an
exact campaign header. Final CSV precedes bundle completion. An explicit later
`--run --resume` validates exact context and all existing journals before new
computation; completed evaluations are reused. Partial/corrupt/conflicting
bytes, foreign contexts, missing completed files and linked output stop without
overwrite/cleanup/automatic retry. Changed source creates another campaign ID.
Candidates are independent and serial; multiprocessing/GPU is not required.

The existing Research page accepts campaign bundles via an additive service
selected by the existing `--research-report` option and Open Report control.
`CompactReportResearchService` remains unchanged. Optional model fields expose
Development rank/parameters/return/drawdown/fills, measured turnover/closed
trades, shortlist/leader, fold count and minimum/median return/maximum drawdown
in the selected details. The existing table, filtering, 2-to-4 comparison and
chart remain read-only. Campaign charts label PerformanceReport turnover
accurately; historical one-way turnover remains separate/unavailable for P3.
Malformed, noncanonical or >10MB artifacts are bounded unavailable states.
No GUI action starts a campaign, trades, modifies results, promotes or opens
holdout. Package public exports load lazily to keep provider/native adapters
out of the campaign import graph; names and requested objects are preserved.
The explicitly authorized scoped authority successor validates the complete
reviewed AST transformation against immutable predecessor exports. Original
historical bytes and source pins remain accepted; security classification is
unchanged. All other import/export/resolver changes fail closed.

P3 source/tests joined the existing Architecture-147 focused/current inventory;
FULL remained GitHub-owned. P3 introduced no new architecture, checkpoint or
146 routing change. Its accepted post-integration sequence was
develop reuse verification: real offline campaign -> bundle review -> existing
Research GUI launch/inspection -> next research step. FINAL_HOLDOUT remains
unopened for strategy selection throughout; no 145 admission is created.

## Deferred Architecture 146 and high-assurance machinery

Architecture 125 rename machinery, Architecture 128 protected redeployment,
Architecture 133 publication/scheduler/install experiments, the Architecture
134 successor-host/release/ACL chain, protected immutable-release publication,
Architecture 146 Administrator/SYSTEM research custody, cross-principal
custody, protected parent provisioning, OPEN-parent ceremony, privileged
observers, and protected attempt claims are LEGACY/DEFERRED. Their source,
tests, and immutable evidence are preserved where they certify historical
behavior; they are not current readiness gates or next actions.

The consumed Architecture 146 observation is preserved exactly at:

    F:\AI\temp\ai-trading-bot-checkpoints\operator-b957c4f6bec54413887316ab17929207\arch146-b-partial-state-readonly-observer\preflight-20261030T053329.017181Z\report.json

It recorded `IDENTITY_STABLE=True`, `OVERALL=BLOCKED`,
`classification=HOST_UNKNOWN`, `stable_repetitions=2`, zero operational
counters, `acquisition_authorized=false`,
`open_parent_creation_authorized=false`, and
`protected_execution=NOT_AUTHORIZED`. It is consumed evidence. There is no
retry, repair, or current observer dispatch.

## Current checkpoint

The current registered checkpoint is `arch147-desktop-supervisor` on
`feature/research-desktop-supervisor-current`, with `preflight=None`,
`execute=None`, and GitHub-owned canonical FULL. The P3 research checkpoint
remains available on its own branch. The normal development route
is focused implementation -> focused tests -> one atomic candidate -> FEATURE +
PROSPECTIVE_DEVELOP admission -> one push -> one CI -> exact review ->
fast-forward `develop`. Source PASS grants no provider or live effect.

## P4 ordinary desktop supervisor

`trading_bot.desktop_runtime` owns lifecycle and immutable bounded health;
`scripts/run_desktop_bot.py` composes it into the existing PySide6 MainWindow.
The optional current Home controls never reinterpret the historical read-only
Supervisor models, adapter, promotion fields or `supervisor_connected=False`.
The current P4 service displays P3 campaign bundles in the same Research page;
the normal historical read-only GUI retains compact-report support as well.

Explicit Start admits one generation: STOPPED -> STARTING -> RUNNING. Exactly
one trading and one research worker run on separate owned non-daemon threads;
one asynchronous coordinator handles startup, health and shutdown outside Qt.
Duplicate Start returns false. Stop is idempotent and signals both workers
before waiting on either: STOPPING -> research closed -> trading reconciled and
closed -> STOPPED. A Stop during startup drains the already-admitted start;
late start acknowledgments remain journaled. There is no automatic restart.

Factories construct only and workers implement small injected start, stop,
bounded close and health interfaces; trading also exposes reconcile-and-close.
Injected blocking operations are bounded by owned operation threads. A timeout
retains ownership, stops the peer and leaves terminal FAILED/attention; it never
force-kills or reports successful closure. Timed-out worker operations cannot
overlap a close, and a late factory result remains owned. Production health
copies only private immutable snapshots; Qt reads cached supervisor facts and
never invokes worker methods. The default per-operation close bound is 2s.
Shutdown waits at most that bound per operation plus 0.1s scheduling allowance
for close; a failed operation does not suppress the peer's shutdown attempt.

P4 trading is deliberately inert: its live thread waits for Stop and reconciles
the empty local lifecycle. It has no strategy, ledger, order, position, file,
broker or research capability. Presentation explicitly says inert trading and
NOT_CONNECTED, deferred to P5; simulated paper is default and LIVE disabled.
Research owns a separate one-slot queue and supports exactly one offline job:
read/strictly verify a bounded local campaign bundle. Its initial production job
checks the accepted P3 campaign/bundle IDs and SHA256, then it remains available.
No campaign runs on Start. Research never receives trading references, risk,
mode, arming, accounts or lifecycle authority. The supervisor shares only health
and artifact identity, with no candidate/configuration selection boundary.
This I/O-only verification needs no CPU research process or multiprocessing
framework. Future CPU-bound campaign execution requires a separate process
composition; it must not enter Qt's event loop.

The ordinary external journal is
`F:\AI\desktop-bot-state\p4\lifecycle.jsonl`. Each fsynced JSONL event has schema
`desktop-runtime/v1`, contiguous sequence, local integer generation, UTC, closed
event and sanitized diagnostic enum. These chronology numbers are not financial
or research-domain identities. Replay rejects duplicate/unknown fields, partial
records, invalid UTC, conflicts and false STOPPED without both worker closure
facts and trading reconciliation. A create-exclusive lifetime lock prevents two
application instances from admitting the same journal. Prior unresolved state,
malformed state, stale ownership or write failure blocks Start. Preserve it for
operator-visible recovery; P4 performs no automatic repair, retry or deletion of
unresolved state. Successful clean close alone releases the ordinary lock.
The journal has a 4 MB admission cap; archival is deferred operator work while
stopped, not a running self-maintenance feature.

Closing the window requests normal asynchronous Stop and keeps Qt alive while
closure completes. Failed/unconfirmed closure refuses window exit and keeps
diagnostics visible. The launcher's finalizer also requests Stop on non-window
Qt exit and cannot report success for unresolved workers. The application has
no update, live, order, promotion or holdout control. Manual updates are allowed
only after a confirmed Stop. No network, provider, credential, account, broker,
scheduler, ACL, final-holdout loader/integrity/admission or protected checkpoint
runner belongs to this composition. P5 will separately compose the accepted
official Robinhood MCP foundations.

P4 source is accepted and integrated on `develop` at
`e5e800ad99da8dd1c09fa36202d5ff8b648c1daf`, tree
`1d2f57afb1d5cddc9487352519f92cced5554f9d`. Original feature CI #815 is
preserved red for missing PySide6 source-gate dependency coverage. Corrective
feature CI #816 is terminal green with canonical FULL, and develop CI #817 is
terminal green with exact-feature certification reuse and no duplicate broad
execution.

The one reviewed no-network owner runtime smoke completed successfully from
`545f21621c15c682f19d10df3a3d1ecf86f8a77c`, tree
`07bb44a2975c44fd62e68a9cc8f3b9f99a0bbd8e`. Generation 1 reached RUNNING
with both workers RUNNING, diagnostic NONE and the accepted P3 campaign/bundle
identity. Stop journaled STOP_REQUESTED, RESEARCH_STOPPED, TRADING_RECONCILED,
TRADING_STOPPED and finally STOPPED as contiguous sequences 5..9, all diagnostic
NONE. The launcher exited 0. P4 runtime acceptance is complete; do not repeat
the smoke.

P5 architecture/design is now current. Its first goal is a useful local
SIMULATED_PAPER worker composed into the existing P4 lifecycle, using local
strategy and deterministic RiskManager authority plus durable restart-safe paper
account state. Robinhood MCP read/review composition follows as a separate P5
slice; broker mutation remains P6.
