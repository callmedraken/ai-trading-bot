# Rolling historical optimized simulation

## Responsibility and boundary

`trading_bot.simulation.rolling_historical` is an orchestration layer over
existing historical scenario generation, optimized paper simulation, and
optimized-simulation performance analytics. It owns no provider, files,
portfolio state, engine, ledger, optimizer, risk calculation, or fill formula.
The caller supplies one `OptimizedPaperPortfolioSimulator`; that simulator's
engine and ledger remain the authoritative mutable state.

The flow is:

`MultiSymbolHistoricalDataResult -> trailing windows -> historical scenarios
-> optimized frames -> one optimized simulation -> one analytics pass`.

## Input and schedule

The request retains an exact, immutable, complete, aligned daily historical
result and an explicit nonempty sequence of rebalance timestamps. Timestamps
are normalized to UTC and must be strictly increasing, unique, and exact frame
timestamps. The fixed trailing `observation_count` is at least two. Every
scheduled point must have a complete window, and a later rebalance cannot occur
before the prior frame's fill timestamp.

Risk and fill reference prices are explicitly `CLOSE`. Submission and fill
offsets are deterministic `timedelta` values satisfying
`0 <= submission_offset <= fill_offset`. They are represented as exact integer
microseconds in identities. The runner never reads a clock.

## Historical validation, slicing, and look-ahead

The source must be an exact `MultiSymbolHistoricalDataResult` with `DAY_1`
frames, a stable ordered universe, strictly increasing timestamps, and a
complete matching bar for each symbol and frame. The runner does not sort,
repair, fill, interpolate, or synthesize observations.

For a rebalance at source index `i`, the child slice is
`[i - observation_count + 1, i + 1)`. It preserves the exact source frame
objects. Its public request starts at the first retained timestamp and ends at
the next source timestamp, or at the original request end for the final source
frame. Child requests and results are built through market-data public
constructors. Consequently, scenario generation can see the rebalance frame
and prior observations only.

One canonical historical fingerprint covers source request semantics, provider
name, ordered universe, completeness information, and every ordered OHLCV bar.
It excludes paths, clocks, object identity, Python hashes, and incidental
mapping order.

## Preparation and execution

Each window produces exactly one deterministic
`HistoricalScenarioGenerationRequest`. The runner calls
`HistoricalReturnScenarioFactory.generate` once and passes the exact generated
scenario set and expected-return tuple into an optimized frame. Frame prices
follow historical universe order and use the rebalance frame's close for both
risk and fill reference prices.

All windows, scenarios, and optimized frames are prepared before execution.
Engine and ledger state fingerprints before and after preparation must match.
The runner then constructs one `OptimizedPaperSimulationRequest` and invokes
the supplied simulator exactly once. Existing per-frame commit semantics apply;
a later failure does not imply whole-run rollback.

After successful simulation, one performance request uses
`FRAME_RISK_PRICES`, retains the exact optimized result, and is analyzed once.
Engine and ledger fingerprints must remain unchanged through analytics.

## Audit, identity, and metadata

`RollingHistoricalFrameGeneration` retains indices, timestamps, the
source-frame fingerprint, scenario request and result, optimized-frame
fingerprint, and exact optimized frame. The aggregate result retains the
rolling request, all frame audits, downstream request/results, and initial and
final component state IDs.

UUID5 identities use the private
`rolling-historical-optimized-simulation-v1` namespace/version. Scenario IDs
bind the rolling request, schedule point, exact window, source fingerprint, and
stage. Optimized request and performance IDs bind their ordered upstream audit
identities. The aggregate identity covers the complete request fingerprint,
historical fingerprint, frame identities, downstream identities, and live
state IDs.

Caller metadata remains on the rolling request. Generated scenario, optimized
request, optimized frame, and performance metadata use separate documented
keys. Caller keys beginning `rolling_historical_simulation_` are reserved, and
optimized request/frame keys do not overlap.

## Reconciliation and failures

Before returning, the runner reconciles schedule order, window endpoints and
sizes, ordered universes, exact scenario handoffs, optimized and analytics
source relationships, frame ordinals, deterministic IDs, and live component
state IDs. Immutable result construction checks retained local relationships
without reslicing history or rerunning generation.

Errors distinguish malformed requests, schedules, windows, scenario
generation, frame/request construction, simulation execution, analytics,
live/source reconciliation, and inconsistent retained results. Known
downstream failures preserve their causes. Analytics failures occur after
simulation has committed and therefore return no rolling aggregate without
claiming rollback.

## Limitations and deferred work

Every generated child result, scenario result, frame, simulation audit, and
analytics audit remains in memory, so long schedules can consume substantial
memory. Schedule factories, exchange-calendar integration, CLI integration,
persistence, recovery/resume, streaming audits, alternative execution prices,
variable windows, networking, brokers, AI, and GPU acceleration are deferred.
