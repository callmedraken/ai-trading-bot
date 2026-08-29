# Architecture 92 — GUI Verified Market-Snapshot Inspection

## Status

GUI-A6a architecture and Qt-free presentation-contract checkpoint.

This checkpoint extends the reviewed GUI foundation with bounded read-only
presentation of one exact **offline-verified daily market-data snapshot artifact**.
It deliberately does not claim that the artifact is the production C3-selected
snapshot. The `feature/gui-foundation` branch does not yet contain the active C3
production selected-snapshot inspection boundary.

The immediate goal is to let the GUI present trustworthy market-snapshot facts
without provider access, Credential Manager access, production SQLite access,
directory discovery, capture controls, or effectful refresh/retry behavior.

## Reviewed source boundary

The existing reviewed verification boundary is:

```text
trading_bot.market_data.verify_daily_snapshot(...)
```

`verify_daily_snapshot` accepts exact snapshot bytes, the identified XNYS
calendar, and optional expected SHA-256/byte-length evidence. A complete `PASS`
result contains one reconstructed `DailyMarketDataSnapshot` and no diagnostics.

A `PASS` already verifies:

- optional expected artifact byte length;
- optional expected artifact SHA-256;
- strict/canonical snapshot parsing;
- retained XNYS calendar identity;
- derived prior-session target consistency;
- complete one-bar-per-requested-symbol coverage;
- bar timestamp/session consistency;
- provider-as-of temporal consistency;
- canonical accepted-bar evidence;
- deterministic snapshot UUID identity;
- retained audit-evidence hash;
- canonical serialization byte equality.

GUI-A6 must consume only a complete `PASS` result. It must never interpret a
partially parsed or failed verification result as usable market data.

## Dependency direction

The allowed direction is:

```text
Qt Market Data page
    -> Qt-free GUI market-data presentation models
    -> GuiApplicationService.get_market_data_state()
    -> reviewed/injected read-only snapshot adapter
    -> verify_daily_snapshot(...)
```

The Qt layer must not import or call `verify_daily_snapshot` directly.

The concrete adapter may receive one explicit snapshot artifact `Path` plus
optional expected SHA-256 and byte-length evidence from the composition layer.
Widgets must not enumerate directories, search for a "latest" snapshot, derive
production selection authority, open production SQLite, or construct C3
capabilities.

## GUI-A6a presentation contract

GUI-A6a introduces immutable Qt-free presentation records:

- `MarketDataPageStatus`: `VERIFIED` or `UNAVAILABLE`;
- `VerifiedMarketSnapshotView`: bounded nonsecret facts from one fully verified
  snapshot artifact;
- `MarketDataPageState`: either one verified snapshot view or one bounded
  unavailable state.

`VerifiedMarketSnapshotView` contains only:

- exact snapshot UUID;
- target XNYS session date;
- requested symbol tuple in retained canonical order, bounded by the existing
  daily-snapshot symbol limit;
- provider ID;
- provider operation;
- provider feed;
- artifact SHA-256 computed by the verifier;
- artifact byte length computed by the verifier;
- retained capture timestamp;
- optional retained provider-as-of timestamp;
- retained source-payload SHA-256;
- retained source-payload byte length;
- retained source-payload media type.

These values are presentation evidence only. `VERIFIED` means the supplied local
artifact passed the existing offline daily-snapshot verifier. It does **not** mean
that C3 selected the artifact for production use, that it is the newest artifact,
or that a new capture is authorized.

## Bounded presentation rules

Presentation models remain Qt-free and fail closed.

- UUIDs remain exact `UUID` values.
- Target session remains an exact `date`.
- Capture/provider-as-of values remain exact timezone-aware `datetime` values.
- Symbols are normalized to bounded presentation strings in canonical request
  order; no sorting or deduplication occurs in the GUI adapter.
- Provider ID/operation/feed and media type are bounded presentation strings
  copied from already-validated snapshot models.
- SHA-256 values must be exact lowercase 64-character hex text.
- Artifact/source-payload byte lengths must be nonnegative exact integers.
- No provider response body, raw audit JSON, credentials, arbitrary exception
  text, or arbitrary filesystem text is retained in presentation state.

## Service contract

`GuiApplicationService` gains:

```text
get_market_data_state() -> MarketDataPageState
```

GUI-A6a keeps existing default GUI startup deterministic and effect-free. The
mock-backed service returns a bounded `UNAVAILABLE` market-data state explaining
that no verified snapshot artifact is connected.

A concrete adapter is deferred to GUI-A6b1 so explicit-path acquisition, artifact
bounds, verification behavior, and failure sanitization can be reviewed
separately from the presentation model.

## Concrete adapter requirements for GUI-A6b1

A future `VerifiedSnapshotInspectionService` may:

1. receive exactly one explicit snapshot artifact `Path`;
2. receive optional expected artifact SHA-256/byte-length evidence;
3. read that exact file once using the existing maximum snapshot artifact bound;
4. construct the existing identified XNYS calendar;
5. call `verify_daily_snapshot(...)` exactly once;
6. map only a complete `PASS` result into `VerifiedMarketSnapshotView`;
7. convert read, verification, parsing, model, calendar, or adaptation failures
   into one bounded `UNAVAILABLE` state without raw exception text.

It must not:

- access the network;
- construct an Alpaca provider or transport;
- read environment credentials or Windows Credential Manager;
- call `capture_daily_snapshot_artifact`;
- open production SQLite or C1/C2/C3 authority;
- enumerate a directory or choose a "latest" artifact;
- write, rename, delete, stage, or repair any artifact;
- replay bars into strategy/paper execution as part of inspection;
- claim production selection authority.

## Qt rendering requirements for GUI-A6b2

The existing Market Data placeholder may be replaced with one immutable
presentation page that obtains its state once during `MainWindow` construction.
Navigation away and back must not reread or reverify the artifact.

The page may render the bounded fields from `VerifiedMarketSnapshotView` and a
human-readable verified/unavailable summary. All model/service-derived strings
must be forced to `Qt.TextFormat.PlainText`.

GUI-A6b2 must not add:

- Capture;
- Refresh;
- Retry;
- Reverify;
- Select;
- Publish;
- Open production database;
- Open Credential Manager;
- provider/network controls;
- recovery controls.

Any such control requires a separate architecture checkpoint.

## Failure behavior

An inability to read or completely verify the explicit artifact becomes a
bounded `UNAVAILABLE` state. Raw exception strings and verification diagnostic
`detail` text are not presented.

GUI-A6 may later add a closed presentation diagnostic vocabulary if operator
needs justify it, but that must mirror reviewed deterministic codes and remain
bounded. A6a does not expose raw diagnostic details.

## Explicit non-goals

GUI-A6 does not:

- identify the production-selected C3 snapshot;
- inspect C3 durable lineage;
- launch or retry market-data capture;
- read production credentials;
- display provider response bodies;
- discover snapshot history;
- provide a file browser/history browser;
- display individual OHLCV bars or charts yet;
- feed a snapshot into a strategy or paper cycle;
- add scheduler, recovery, publication, or selection controls.

## Future C3 integration

After the active C3 branch is merged through its own reviewed process, a later
architecture checkpoint may implement a production-selected-snapshot adapter.
That adapter should target the same `MarketDataPageState` presentation contract
where possible, but it must obtain selection through a reviewed read-only C3
application/authority boundary rather than querying SQLite or capture-output
files from Qt code.

The distinction must remain explicit in presentation: an offline verified
artifact is not automatically a production-selected artifact.

## Testing contract

GUI-A6a pure-Python tests must prove:

1. verified/unavailable state invariants reject contradictory payloads;
2. snapshot UUID/date/timestamp/evidence types and bounds are enforced;
3. symbols preserve canonical supplied order and remain bounded;
4. SHA-256 and byte-length presentation evidence is strict;
5. provider/media-type presentation strings are bounded;
6. default GUI services return deterministic `UNAVAILABLE` market-data state;
7. `GuiApplicationService` remains Qt-free;
8. no market-data provider, network, Credential Manager, production SQLite, or
   C3 dependency is introduced by A6a.

GUI-A6b1 tests will cover explicit artifact reads, exact one-shot verifier calls,
PASS mapping, bounded failure conversion, and no-effect behavior. GUI-A6b2 tests
will cover native Qt rendering, literal plain-text handling, no action controls,
and no reinspection on navigation.

## Model routing

Architecture/data-boundary selection for A6a/A6b1 requires Sol Medium. Once the
contract and adapter are accepted, the mechanical Qt rendering step A6b2 is
appropriate for Luna Extra High. Any attempt to read production C3 authority,
credentials, or effect-ordering state requires Sol High review instead.
