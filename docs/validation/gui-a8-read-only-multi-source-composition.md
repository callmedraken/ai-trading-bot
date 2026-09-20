# GUI-A8 Read-Only Multi-Source Composition Validation Plan

## 1. Purpose

Validate Architecture 115,
`docs/architecture/115-gui-read-only-multi-source-composition.md`.

GUI-A8 makes already-reviewed read-only GUI adapters usable together through one
safe startup/composition layer. It does not add new operational authority.

## 2. A8a architecture gate

Freeze before source implementation:

- the Qt-free startup configuration;
- exact CLI artifact-selection arguments;
- GENESIS versus successor proof mutual exclusion;
- all-four successor proof requirement;
- existing adapter reuse;
- Paper Operation remains unavailable absent already-verified inputs;
- Operations remains unavailable during ordinary startup;
- no directory discovery or "latest" selection;
- no production O2/C1/C2/C3/provider/credential/broker/scheduler/effect path.

## 3. A8b startup configuration tests

Add pure-Python tests for the startup configuration and parser.

They must cover:

- empty/default configuration;
- research-only;
- market-data snapshot with/without matching evidence fields;
- GENESIS paper-account selection;
- successor four-artifact selection;
- GENESIS plus successor contradiction;
- each partial successor proof combination fails;
- evidence without corresponding artifact fails;
- byte length rejects bool/negative/non-int;
- SHA validation follows the existing adapter/verifier contract;
- recognized GUI arguments are removed from Qt argument forwarding.

Configuration validation must occur before GUI construction.

## 4. A8b composite service tests

The composite service must be tested with injected/fake leaf services where
useful and with real existing adapters for representative fixtures.

Prove:

- `get_research_state()` delegates only to the configured research service;
- `load_research_report(path)` retains the existing explicit Research behavior;
- `get_market_data_state()` delegates to the existing verified-snapshot adapter;
- `get_paper_account_state()` delegates to exactly one accepted paper-account
  adapter;
- `get_paper_state()` remains deterministic unavailable;
- `get_operator_observability_state()` remains deterministic unavailable;
- no leaf adapter is called merely because another page is configured;
- raw adapter exceptions do not escape if the accepted leaf adapter already
  sanitizes them.

## 5. A8c real-adapter integration tests

Use existing repository fixtures/builders; do not add production artifacts.

At minimum verify:

```text
Research + verified snapshot + GENESIS checkpoint
Research + verified snapshot + successor edge
default/no artifacts
missing/invalid artifact -> bounded UNAVAILABLE for that page only
```

The presence or failure of one read-only source must not grant authority to or
silently replace another source.

## 6. Startup no-effect gate

Monkeypatch/prohibit at least:

- `read_personal_desktop_operator_observability_snapshot`;
- production C1 acquisition/validation;
- provider capture/network constructors;
- D8-A qualification;
- D8-B settlement execution;
- receipt recovery;
- Task Scheduler mutation;
- broker submission.

Normal GUI-A8 startup, including artifact-backed startup, must not reach any of
them.

## 7. MainWindow regression gate

Run the entire GUI suite because `GuiApplicationService` composition/startup is
changing.

Any stale test fake that only lacks the frozen service surface should be updated
to deterministic unavailable state. Do not add a production fallback to
`MainWindow`.

Navigation must remain:

```text
home
research
paper
paper-account
market-data
operations
system
```

## 8. Focused implementation sequence

Recommended source sequence:

1. A8b1 startup configuration + parser contract;
2. A8b2 composite service;
3. A8c real adapter startup wiring;
4. A8d Qt/startup regression and visual polish;
5. complete `tests/gui`;
6. Ruff check/format on touched source/tests;
7. `git diff --check`.

Use fresh external `--basetemp` under `F:\AI\temp\pytest\...` and
`-p no:cacheprovider` for Windows pytest runs.

## 9. Visual gate

Launch explicit combinations without production authority:

```text
default
research + market data + GENESIS paper account
research + market data + successor paper account
```

Verify truthful page labels, no action/effect controls, stable navigation, and no
layout regression at normal/minimum sizes.

## 10. Final certification

After the final semantic source tree and visual PASS:

1. run complete repository pytest once, preserving the Architecture-77 clean
   harness rule if the local worktree hits the known fixed cache-path condition;
2. run Ruff check on the repository;
3. run Ruff format check on the repository;
4. run `git diff --check`;
5. verify exact HEAD/tree/status;
6. perform independent GitHub diff review.

Docs-only closeout after accepted source certification does not require another
full suite.

## 11. Stop conditions

Stop and review before proceeding if implementation requires:

- production O2 invocation during ordinary GUI startup;
- C1/C2/C3 or Credential Manager access;
- provider/network access;
- directory enumeration or "latest" selection;
- reconstruction of `VerifiedPaperOperationExecutionInputs` from GUI arguments;
- paper/settlement/recovery/scheduler/broker effects;
- changes to deterministic identities or serialized artifacts;
- changes to D5/D8/D9 operational state.

Any such requirement is outside GUI-A8.

## 12. Next milestone after A8

After GUI-A8 acceptance, the next safe GUI candidate is a separate GUI-A9
read-only System Health / Audit milestone built only from reviewed bounded
diagnostic sources. Operational controls remain deferred until their underlying
authority boundaries are separately accepted.
