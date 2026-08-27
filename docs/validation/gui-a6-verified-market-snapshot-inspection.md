# GUI-A6 verified market-snapshot inspection validation plan

## 1. Purpose

This plan validates Architecture 92,
`docs/architecture/92-gui-verified-market-snapshot-inspection.md`.

GUI-A6 presents one exact local daily-snapshot artifact only after the existing
offline verifier accepts it completely. This plan does not validate or claim C3
production selection authority.

## 2. A6a contract gate

Before implementation, freeze Qt-free presentation models for:

```text
MarketDataPageStatus
  VERIFIED
  UNAVAILABLE

VerifiedMarketSnapshotView
  snapshot_id
  target_session_date
  symbols
  provider_id
  provider_operation
  provider_feed
  artifact_sha256
  artifact_byte_length
  captured_at
  provider_as_of
  source_payload_sha256
  source_payload_byte_length
  source_payload_media_type

MarketDataPageState
  status
  message
  snapshot
```

The exact names may change during implementation only if the architecture is
updated first; semantics must remain equivalent.

Tests must prove:

- `VERIFIED` requires exactly one complete view;
- `UNAVAILABLE` requires no view;
- messages are nonblank bounded presentation text;
- snapshot ID is exact UUID;
- session date is exact `date`;
- capture/provider-as-of are exact timezone-aware datetimes, with
  provider-as-of optional;
- symbols are nonempty, unique, bounded, and preserve supplied order;
- provider/media-type text is nonblank and bounded;
- SHA-256 fields are lowercase 64-character hex;
- byte lengths are nonnegative exact integers.

## 3. GUI service gate

`GuiApplicationService` gains exactly one new read-only method:

```text
get_market_data_state() -> MarketDataPageState
```

Every existing concrete/fake implementation used by tests must satisfy the
expanded protocol.

Default mock-backed startup returns deterministic `UNAVAILABLE` state and must
remain provider/network/production-authority free.

The service protocol and presentation models remain importable without PySide6.

## 4. A6b1 explicit artifact adapter gate

The concrete adapter receives:

- one explicit snapshot `Path`;
- optional expected artifact SHA-256;
- optional expected artifact byte length.

It must not discover those values by scanning directories or production state.

Before verification, enforce the existing maximum snapshot artifact byte bound.
The adapter then constructs the existing identified XNYS calendar and calls:

```text
verify_daily_snapshot(...)
```

exactly once for one service-state acquisition.

Only `DailySnapshotVerificationStatus.PASS` with a complete snapshot may map to
`VERIFIED` presentation state.

## 5. PASS mapping gate

For a complete verifier PASS, tests prove exact mapping of:

- snapshot UUID;
- target session date;
- requested symbol order;
- provider ID, operation, and feed;
- verifier-computed artifact SHA-256 and byte length;
- retained captured-at timestamp;
- optional retained provider-as-of timestamp;
- retained source-payload SHA-256, byte length, and media type.

The adapter must not recompute or reinterpret snapshot identity, target session,
canonical bars, or provider semantics after verifier PASS.

## 6. Failure sanitization gate

The following all become bounded `UNAVAILABLE` state:

- missing/unreadable artifact;
- oversized artifact;
- invalid optional expected evidence;
- verification FAIL;
- parser/model/calendar/serialization errors;
- unexpected adaptation error.

Raw exception strings and verifier diagnostic `detail` text must not be copied
into presentation state.

Tests may assert closed/generic presentation messages, but no filesystem-native,
provider-native, or parser-native raw text may escape.

## 7. No-effect gate

Focused tests must prove GUI-A6 adapter/model work does not:

- construct an Alpaca provider or transport;
- perform network access;
- read environment credentials;
- read Windows Credential Manager;
- call daily-snapshot capture;
- open production SQLite;
- acquire C1/C2/C3 capability;
- mutate files;
- enumerate directories;
- execute strategy/risk/paper flows.

The only permitted external read in A6b1 is the one explicitly supplied local
snapshot artifact.

## 8. A6b2 Qt rendering gate

Replace only the existing Market Data placeholder.

The page obtains `get_market_data_state()` once during `MainWindow`
construction. Navigation away/back must not call the service again.

For `UNAVAILABLE`, render only a bounded status/message.

For `VERIFIED`, render the Architecture-92 fields read-only. Every
service/model-derived `QLabel` must use `Qt.TextFormat.PlainText`.

The page must contain no buttons or controls whose semantics imply:

```text
capture
refresh
retry
reverify
select
publish
recover
open credential manager
open production database
```

## 9. Regression compatibility gate

Because `GuiApplicationService` expands again, run the entire `tests/gui`
directory before final certification to catch stale fake-service fixtures, not
only A6-focused tests.

If an older fake service fails solely because it lacks `get_market_data_state()`,
update that test fixture to return deterministic unavailable state. Do not add a
production fallback to `MainWindow` to accommodate incomplete test doubles.

## 10. Focused test sequence

Recommended development sequence:

1. A6a pure model/service tests;
2. A6b1 adapter tests with verifier injected or monkeypatched at the adapter
   boundary where appropriate;
3. A6b2 offscreen Qt tests;
4. complete `tests/gui` integration suite;
5. Ruff check/format on touched GUI/tests;
6. `git diff --check`.

Do not run the full repository suite repeatedly during iteration.

## 11. Visual gate

After automated GUI integration passes, launch the native GUI normally and
inspect both deterministic unavailable state and one synthetic/injected verified
presentation state.

Verify:

- Market Data page fits the existing dark theme;
- long hashes/UUIDs remain readable/selectable without breaking layout;
- symbol presentation remains bounded;
- timestamps/session/provider fields are understandable;
- no action/effect controls appear;
- navigation causes no visible reinspection behavior or layout regression.

## 12. Final certification

After the final accepted implementation tree and visual PASS:

1. run the complete repository pytest suite once;
2. run Ruff check on `src tests`;
3. run Ruff format check on `src tests`;
4. run `git diff --check`;
5. inspect `git status --short` and preserve unrelated generated/untracked
   artifacts;
6. perform exact GitHub diff review from the last accepted GUI checkpoint.

## 13. Acceptance statement

GUI-A6 is accepted only if the final evidence can state:

```text
OFFLINE_SNAPSHOT_VERIFIER_REUSED=True
EXPLICIT_ARTIFACT_ONLY=True
DIRECTORY_DISCOVERY=False
PRODUCTION_SQLITE_ACCESS=False
C3_AUTHORITY_ACCESS=False
CREDENTIAL_MANAGER_ACCESS=False
NETWORK_ACCESS=False
CAPTURE_CONTROL_PRESENT=False
GUI_INTEGRATION=PASSED
VISUAL_GATE=PASSED
FULL_REGRESSION=PASSED
```

A6 acceptance means the GUI can truthfully display one fully offline-verified
snapshot artifact. It does not mean the GUI knows which artifact production C3
selected.
