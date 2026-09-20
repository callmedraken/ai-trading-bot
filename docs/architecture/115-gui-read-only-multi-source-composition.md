# Architecture 115 — GUI-A8 Read-Only Multi-Source Composition

## Status

GUI-A8 architecture contract. This checkpoint extends the accepted GUI-A1
through GUI-A7 and PD4 operator-observability presentation work with one bounded
startup/composition layer for already-reviewed read-only adapters.

GUI-A8 does not add trading, market-data capture, decision publication,
settlement, recovery, scheduler mutation, credential access, brokerage access,
or live controls.

## Goal

Make the existing read-only GUI capabilities usable together from normal desktop
startup without weakening their existing adapter boundaries.

The GUI currently has reviewed pages/adapters for:

- compact historical research reports;
- one explicit offline-verified market-data snapshot;
- one explicit offline-verified paper-account checkpoint or successor edge;
- one exact paper-operation inspection when already-verified operation inputs are
  supplied by composition;
- bounded PD4 operator-observability presentation.

Normal `python -m trading_bot.gui` startup, however, only composes an optional
research report. The remaining pages normally stay in deterministic
`UNAVAILABLE` state.

GUI-A8 closes only that composition gap for adapters whose safe explicit inputs
already exist.

## Dependency direction

The allowed direction remains:

```text
Qt pages
  -> immutable GUI presentation state
  -> GuiApplicationService
  -> GUI-A8 composite read-only service
  -> existing reviewed read-only adapters
  -> existing verifier / presentation boundaries
```

The composite service may delegate to existing adapters. It must not duplicate
verification, accounting, strategy, authority, or identity logic.

The following remain forbidden:

```text
GUI -> production SQLite
GUI -> Credential Manager
GUI -> provider transport
GUI -> broker transport
GUI -> Task Scheduler mutation
GUI -> settlement / recovery effect
GUI -> directory discovery / "latest" selection
GUI -> independent trading/risk/authority logic
```

## A8a startup configuration contract

GUI-A8 introduces one Qt-free immutable startup configuration carrying only
explicit read-only artifact selections and optional expected artifact evidence.

The configuration may contain:

```text
research_report: Path | None

market_data_snapshot: Path | None
market_data_expected_sha256: str | None
market_data_expected_byte_length: int | None

paper_account_genesis: Path | None
paper_account_expected_sha256: str | None
paper_account_expected_byte_length: int | None

paper_account_prior: Path | None
paper_account_snapshot: Path | None
paper_account_cycle_report: Path | None
paper_account_successor: Path | None
paper_account_successor_expected_sha256: str | None
paper_account_successor_expected_byte_length: int | None
```

The configuration must reject contradictory or partial paper-account proof
selection:

- GENESIS mode requires exactly one explicit GENESIS checkpoint and no successor
  proof paths;
- successor mode requires all four explicit proof paths and no GENESIS path;
- omitting all paper-account inputs is valid and yields `UNAVAILABLE`;
- expected evidence is valid only for the corresponding selected artifact mode.

No field may select an account ID, execution session, operation identity,
provider, credential, production authority, scheduler action, or effect gate.

## A8b composite service contract

Introduce one composite implementation of `GuiApplicationService` that owns or
delegates to:

- `CompactReportResearchService` for the optional startup research artifact;
- `VerifiedSnapshotInspectionService` for the optional market-data snapshot;
- `VerifiedGenesisPaperAccountInspectionService` for explicit GENESIS mode;
- `VerifiedSuccessorPaperAccountInspectionService` for explicit successor-edge
  mode;
- deterministic unavailable state for Paper Operation unless an already-reviewed
  paper inspection service is explicitly injected by a later composition
  boundary;
- deterministic unavailable state for Operations during ordinary GUI startup.

The composite service must not invoke production O2, D8-A, G5/G6, C1, C2, C3,
provider transport, Credential Manager, or broker APIs.

Each page state is acquired once by `MainWindow` at construction, preserving the
existing navigation contract. Navigation must not trigger rereads, reverification,
provider calls, or any effect.

The Research page retains its already-reviewed explicit Open Report behavior
through `load_research_report(path)`.

## A8c startup CLI contract

Normal module startup may add explicit artifact-selection arguments for the
read-only composition.

The exact CLI names are:

```text
--research-report PATH

--market-data-snapshot PATH
--market-data-sha256 HEX
--market-data-byte-length N

--paper-account-genesis PATH
--paper-account-sha256 HEX
--paper-account-byte-length N

--paper-account-prior PATH
--paper-account-snapshot PATH
--paper-account-cycle-report PATH
--paper-account-successor PATH
--paper-account-successor-sha256 HEX
--paper-account-successor-byte-length N
```

Parser/configuration validation must reject contradictory or partial
paper-account selections before GUI construction.

Optional expected SHA/byte-length values are presentation-verifier evidence only.
They are not authority inputs.

Unknown Qt arguments may still be passed through using the existing startup
split, but recognized GUI-A8 arguments must not be forwarded to Qt.

## Paper Operation boundary

GUI-A8 does not invent a startup path for `PaperOperationInspectionService`.

That service requires one explicit operation root plus
`VerifiedPaperOperationExecutionInputs`. GUI-A8 must not reconstruct those
verified inputs from caller-selected IDs, paths, or serialized fragments merely
to make the page available.

The Paper page therefore remains deterministically unavailable under ordinary
GUI-A8 startup unless a future separately reviewed composition boundary provides
already-verified inputs.

## Operations boundary

Ordinary GUI-A8 startup must not invoke
`read_personal_desktop_operator_observability_snapshot()`.

The accepted Operations page remains available for injected bounded state in
tests/specialized composition, but normal desktop startup returns deterministic
`UNAVAILABLE`.

A future production-observability startup mode requires its own architecture
because it would touch C1/current durable state under the dedicated Trading
principal.

## Failure behavior

All existing adapters retain their fail-closed behavior.

For startup configuration errors:

- malformed/contradictory argument combinations fail before `QApplication` /
  `MainWindow` construction;
- error text is bounded and must not echo sensitive artifact contents;
- missing/unreadable/invalid artifact files are handled by the existing adapters
  as bounded `UNAVAILABLE` states rather than raw exceptions.

The composite service does not catch and reinterpret verifier results. It
delegates to the accepted adapters.

## UI scope

GUI-A8 does not redesign the existing pages. It may make small presentation
changes needed to clarify that:

- Research is local historical research;
- Market Data is one explicit offline-verified snapshot;
- Paper Account is one explicit offline-verified checkpoint/edge;
- Paper and Operations remain unavailable unless a separately reviewed service
  is injected.

No new effect button is permitted.

## Testing contract

Focused tests must prove:

1. exact startup configuration invariants;
2. default startup returns deterministic unavailable Market Data, Paper Account,
   Paper, and Operations state;
3. one explicit valid market-data snapshot is delegated to
   `VerifiedSnapshotInspectionService`;
4. one explicit valid GENESIS checkpoint is delegated to
   `VerifiedGenesisPaperAccountInspectionService`;
5. one complete successor proof set is delegated to
   `VerifiedSuccessorPaperAccountInspectionService`;
6. partial or contradictory paper-account selections fail before Qt
   construction;
7. expected SHA/length arguments are forwarded only to their existing adapter;
8. GUI startup never invokes production O2, C1/C2/C3, provider capture,
   settlement, recovery, scheduler mutation, or brokerage;
9. `MainWindow` still acquires each state once and navigation remains
   presentation-only;
10. the entire `tests/gui` suite remains green before visual/final
    certification.

## Visual gate

Inspect at least:

- default all-unavailable read-only startup;
- startup with Research + Market Data + GENESIS Paper Account;
- startup with successor-edge Paper Account;
- minimum supported window size.

Confirm:

- navigation remains stable;
- artifact-backed pages clearly say offline/read-only;
- long IDs/digests remain readable/selectable;
- no effect controls appear;
- unavailable Paper/Operations states remain truthful;
- existing Research comparison, Paper Account, Market Data, and Operations
  layouts do not regress.

## Model routing

- A8a architecture/validation: ChatGPT/Sol.
- A8b startup configuration + composite service: Luna Extra High once A8a is
  accepted.
- A8c parser/startup wiring and focused regression fixes: Luna Extra High.
- Escalate to Astra only if implementation reveals hidden cross-module coupling
  outside the frozen contract.
- Any production O2/Trading-principal composition or authority-state discovery:
  Sol High and a separate architecture checkpoint.

## Explicit non-goals

GUI-A8 does not:

- add paper execution, settlement, recovery, capture, publication, scheduler, or
  broker controls;
- identify a "current/latest" market snapshot or account checkpoint by scanning;
- inspect directories or production databases;
- infer paper-operation verified inputs;
- invoke production operator observability at ordinary startup;
- change deterministic identities or serialized artifacts;
- modify D5/D8/D9 operational state;
- advance PD5 broker-paper or live trading.

## Acceptance

GUI-A8 is accepted only when final evidence can state:

```text
MULTI_SOURCE_READ_ONLY_COMPOSITION=True
EXPLICIT_ARTIFACT_SELECTION_ONLY=True
DIRECTORY_DISCOVERY=False
LATEST_SELECTION=False
PRODUCTION_O2_STARTUP=False
C1_C2_C3_ACCESS=False
CREDENTIAL_MANAGER_ACCESS=False
PROVIDER_NETWORK_ACCESS=False
PAPER_EXECUTION=False
SETTLEMENT_EFFECT=False
RECOVERY_EFFECT=False
SCHEDULER_MUTATION=False
BROKERAGE_ACCESS=False
GUI_INTEGRATION=PASSED
VISUAL_GATE=PASSED
FULL_REGRESSION=PASSED
```
